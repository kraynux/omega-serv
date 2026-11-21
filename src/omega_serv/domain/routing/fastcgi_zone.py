"""Configuration FastCGI (spec §21). Au depart UN SEUL couple prefixe URL / racine d'execution
(OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6). Projets 3.0.0 §8.1 (decision de l'auteur du 2026-11-15) : une LISTE de
zones (`settings["zones"]`), chacune avec ses reglages et son propre interrupteur, pour arreter une zone le
temps d'une maintenance de ses fichiers sans couper les autres. La regle de confinement reste la meme, zone par
zone (racine des scripts hors webroot). Une ancienne configuration (un seul enregistrement a plat) reste lue
comme une zone unique ; l'ecran FastCGI l'ecrit au nouveau format a son premier enregistrement.

omega-serv ne transmet jamais de valeur PHP (`PHP_VALUE`, `PHP_ADMIN_VALUE`) : sur un meme pool PHP-FPM, une
valeur passee ainsi deborde sur les requetes suivantes des autres zones. Des reglages PHP differents passent par
un pool PHP-FPM par zone (une socket par zone), que l'administrateur configure lui-meme."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from omega_serv.core.i18n import _


@dataclass(frozen=True)
class FastCgiConfig:
    url_prefix: str = "/app/"
    script_root: str = ""
    socket_path: str = "var/run/php-fpm.sock"
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    allowed_extensions: tuple[str, ...] = (".php",)
    index_files: tuple[str, ...] = ("index.php",)
    allowed_scripts: tuple[str, ...] = ()
    """Liste blanche optionnelle de scripts d'entree, en chemin relatif
    a script_root (ex. "index.php", "api/router.php") - retour
    utilisateur 2026-09-09 : par defaut (tuple vide) tout fichier sous
    script_root dont l'extension est dans allowed_extensions reste
    executable (comportement historique, retro-compatible). Une fois
    renseignee, SEULS ces scripts precis sont executables - un fichier
    .php d'inclusion non liste (helper, config, vendor/) redevient
    inaccessible directement en URL meme s'il est toujours dans
    allowed_extensions."""
    enabled: bool = True
    """Interrupteur de la zone (§8.1) : une zone arretee repond 503 (maintenance) sur tout son prefixe, sans
    retomber sur les fichiers du webroot ni sur une autre zone ; l'option `fastcgi` reste l'interrupteur general."""
    max_request_size: int | None = None
    """Taille maximale du corps d'une requete vers cette zone, en octets (projets 3.0.0 §9, decision de l'auteur du
    2026-11-16) : par exemple de gros envois sur une zone d'administration. None : la taille globale de l'ecran
    Limites (`server.max_request_size`). Peut etre plus grande ou plus petite que la taille globale."""


ZONE_KEYS: tuple[str, ...] = ("url_prefix", "script_root", "socket_path", "connect_timeout_seconds",
                              "read_timeout_seconds", "allowed_extensions", "index_files", "allowed_scripts",
                              "max_request_size")

MAX_REQUEST_SIZE_CEILING = 1 << 50
"""Plafond de la taille par zone : celui que le moteur natif accepte pour `server.max_request_size`."""


def parse_fastcgi_config(settings: dict[str, Any]) -> FastCgiConfig:
    defaults = FastCgiConfig()
    return FastCgiConfig(
        url_prefix=settings.get("url_prefix", defaults.url_prefix),
        script_root=settings.get("script_root", defaults.script_root),
        socket_path=settings.get("socket_path", defaults.socket_path),
        connect_timeout_seconds=float(settings.get("connect_timeout_seconds", defaults.connect_timeout_seconds)),
        read_timeout_seconds=float(settings.get("read_timeout_seconds", defaults.read_timeout_seconds)),
        allowed_extensions=tuple(settings.get("allowed_extensions", defaults.allowed_extensions)),
        index_files=tuple(settings.get("index_files", defaults.index_files)),
        allowed_scripts=tuple(settings.get("allowed_scripts", defaults.allowed_scripts)),
        enabled=settings.get("enabled", True) is not False,
        max_request_size=_optional_size(settings.get("max_request_size")),
    )


def _optional_size(value: Any) -> int | None:
    """Absente ou vide : None (taille globale). Une valeur non entiere est gardee telle quelle pour que la
    validation la refuse avec un message, jamais convertie en silence."""
    if value is None or value == "":
        return None
    return value  # type: ignore[no-any-return]


def fastcgi_zone_entries(settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Enregistrements bruts des zones : `settings["zones"]` s'il existe, sinon l'ancien enregistrement a plat
    (une zone), sinon aucune."""
    zones = settings.get("zones")
    if zones is not None:
        return [zone for zone in zones if isinstance(zone, dict)] if isinstance(zones, list) else []
    if any(key in settings for key in ZONE_KEYS):
        return [{key: settings[key] for key in ZONE_KEYS if key in settings}]
    return []


def parse_fastcgi_zones(settings: dict[str, Any]) -> tuple[FastCgiConfig, ...]:
    return tuple(parse_fastcgi_config(entry) for entry in fastcgi_zone_entries(settings))


def active_socket_paths(settings: dict[str, Any]) -> tuple[str, ...]:
    """Sockets PHP-FPM des zones actives, sans doublon, dans l'ordre (sonde des capacites)."""
    return tuple(dict.fromkeys(zone.socket_path for zone in parse_fastcgi_zones(settings)
                               if zone.enabled and zone.socket_path))


def fastcgi_zone_settings(zone: FastCgiConfig) -> dict[str, Any]:
    return {
        "url_prefix": zone.url_prefix,
        "enabled": zone.enabled,
        "script_root": zone.script_root,
        "socket_path": zone.socket_path,
        "connect_timeout_seconds": zone.connect_timeout_seconds,
        "read_timeout_seconds": zone.read_timeout_seconds,
        "allowed_extensions": list(zone.allowed_extensions),
        "index_files": list(zone.index_files),
        "allowed_scripts": list(zone.allowed_scripts),
        **({"max_request_size": zone.max_request_size} if zone.max_request_size is not None else {}),
    }


def fastcgi_settings_with_zones(settings: dict[str, Any], zones: list[FastCgiConfig]) -> dict[str, Any]:
    """Reglages de l'option au nouveau format : les cles de l'ancien enregistrement a plat sont retirees."""
    kept = {key: value for key, value in settings.items() if key not in ZONE_KEYS and key != "zones"}
    return {**kept, "zones": [fastcgi_zone_settings(zone) for zone in zones]}


def validate_fastcgi_zones_structure(zones: tuple[FastCgiConfig, ...]) -> list[str]:
    """Erreurs de chaque zone, prefixees par la zone, et prefixes en double (seule la premiere servirait)."""
    errors: list[str] = []
    seen: set[str] = set()
    for zone in zones:
        errors.extend(_("zone {prefix!r} : {error}").format(prefix=zone.url_prefix, error=error)
                      for error in validate_fastcgi_config_structure(zone))
        key = zone.url_prefix.rstrip("/") or "/"
        if key in seen:
            errors.append(_("zone {prefix!r} : préfixe en double").format(prefix=zone.url_prefix))
        seen.add(key)
    return errors


def validate_fastcgi_config_structure(config: FastCgiConfig) -> list[str]:
    """Validation structurelle pure - la porte bloquante "script_root
    hors webroot" exige les chemins projet reels et vit dans
    application/config/validate_config.py."""
    errors: list[str] = []
    if not config.url_prefix.startswith("/"):
        errors.append(_("url_prefix doit commencer par '/' : {url_prefix!r}").format(url_prefix=config.url_prefix))
    if not config.script_root:
        errors.append(_("script_root ne peut pas être vide"))
    if not config.socket_path:
        errors.append(_("socket_path ne peut pas être vide"))
    if not config.allowed_extensions:
        errors.append(_("allowed_extensions ne peut pas être vide"))
    if config.connect_timeout_seconds <= 0:
        errors.append(_("connect_timeout_seconds doit être strictement positif"))
    if config.read_timeout_seconds <= 0:
        errors.append(_("read_timeout_seconds doit être strictement positif"))
    size = config.max_request_size
    if size is not None and (not isinstance(size, int) or isinstance(size, bool)
                             or not 0 < size <= MAX_REQUEST_SIZE_CEILING):
        errors.append(_("max_request_size doit être un nombre entier d'octets strictement positif (vide = taille "
                        "de l'écran Limites)"))
    if any(not name or name.startswith("/") for name in config.allowed_scripts):
        errors.append(_("allowed_scripts doit contenir des chemins relatifs non vides (pas de '/' en tête)"))
    return errors
