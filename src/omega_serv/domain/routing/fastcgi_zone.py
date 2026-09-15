# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Configuration FastCGI (spec §21). Modele de zone volontairement
simplifie (OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6) : UN SEUL couple
prefixe URL / racine d'execution, pas une liste de zones PHP - decision
explicite pour reduire la surface de configuration et garder la regle
de confinement triviale a auditer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    )


def validate_fastcgi_config_structure(config: FastCgiConfig) -> list[str]:
    """Validation structurelle pure - la porte bloquante "script_root
    hors webroot" exige les chemins projet reels et vit dans
    application/config/validate_config.py."""
    errors: list[str] = []
    if not config.url_prefix.startswith("/"):
        errors.append(f"url_prefix doit commencer par '/' : {config.url_prefix!r}")
    if not config.script_root:
        errors.append("script_root ne peut pas etre vide")
    if not config.socket_path:
        errors.append("socket_path ne peut pas etre vide")
    if not config.allowed_extensions:
        errors.append("allowed_extensions ne peut pas etre vide")
    if config.connect_timeout_seconds <= 0:
        errors.append("connect_timeout_seconds doit etre strictement positif")
    if config.read_timeout_seconds <= 0:
        errors.append("read_timeout_seconds doit etre strictement positif")
    if any(not name or name.startswith("/") for name in config.allowed_scripts):
        errors.append("allowed_scripts doit contenir des chemins relatifs non vides (pas de '/' en tete)")
    return errors
