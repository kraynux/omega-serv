"""Moteur HTTP effectif : UNE seule fonction decide, tout le monde l'affiche (plan moteur C++ §16.5, exigence
utilisateur 2026-11-02 : « eviter le melange des genres [...] que cela soit bien explicite »).

`decide_engine` est appelee par `serve` au demarrage, par le rechargement (SIGHUP), par l'ecran Etat et par
`omega-serv engine status` : ce que l'interface annonce est toujours ce qui tournera, jamais deux regles qui
divergent. Le natif n'est jamais lance pour une configuration qu'il ne sait pas servir entierement : une seule
fonction non prise en charge = repli complet sur le moteur Python (plan §6), jamais un serveur partiel.

Les raisons sont des codes stables (journal, fichier d'etat, tests) ; leur texte affiche passe par
`describe_reason` (traduit) et `log_reason` (journal, francais fixe comme le reste d'error.log)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_engine import parse_proxy_engine_settings
from omega_serv.domain.routing.proxy_zone import (
    ProxyZone,
    normalize_host_address,
    parse_proxy_zones,
)

NATIVE_BINARY_RELATIVE_PATH = "bin/omega-http-core"
"""Produit par build-release.sh (plan §7.3), jamais versionne."""

NATIVE_OPTION_GAPS: tuple[str, ...] = ()
"""Options que le natif ne sait pas servir : aucune depuis le lot 6. WAF, Auth et Active Defense passent par le
processus Python de securite (lot 4), le listing par une route deleguee (lot 5), FastCGI / envoi de fichiers par une
connexion confiee a Python (lot 6) ; reverse proxy et WebSocket relayes par le natif (plan proxy natif v2, lots 4 a 11),
sauf les zones avec cache (confiees)."""

APPLICATION_OPTIONS = ("upload", "fastcgi", "reverse_proxy")
TLS_HANDOFF = "tls_handoff"
"""TLS direct + route applicative : la connexion chiffree par le natif ne peut pas etre confiee a Python."""

BINARY_MISSING = "binary_missing"
BINARY_NOT_EXECUTABLE = "binary_not_executable"
WORKERS_IGNORED = "workers_ignored"  # avis, jamais une cause de repli


@dataclass(frozen=True)
class EngineDecision:
    requested: str
    effective: str
    reasons: tuple[str, ...] = ()
    """Pourquoi le moteur effectif differe du moteur demande (vide sinon)."""
    notices: tuple[str, ...] = ()
    """Reglages sans effet avec ce moteur (ex. workers du mode boost avec le natif)."""

    @property
    def fallback(self) -> bool:
        return self.requested != self.effective


def native_unsupported_features(config: OmegaServConfig) -> list[str]:
    """Fonctions actives que le natif ne prend pas encore en charge : une seule entree = repli moteur Python."""
    # TLS direct pris en charge depuis le lot 3b (OpenSSL, meme contexte que Python) : jamais une cause de repli.
    missing = [option for option in NATIVE_OPTION_GAPS if config.option_enabled(option)]
    if tls_direct(config) and (config.option_enabled("upload") or config.option_enabled("fastcgi")
                               or any(zone.engine == "python" for zone in decide_proxy_zones(config))):
        # Plan proxy natif v2, lot 3 (Q8 amendee par P7) : seule une zone CONFIEE a Python demande la connexion en
        # clair ; une zone relayee par le natif se sert avec son TLS.
        missing.append(TLS_HANDOFF)
    return missing


def tls_direct(config: OmegaServConfig) -> bool:
    return config.tls.enabled and config.tls.mode == "direct"


# ---------------------------------------------------------------------------------------------------------------------
# Plan proxy natif v2, lot 3 : zones natives ou confiees (§5.2), option options.reverse_proxy.engine (P8), regles TLS
# de `config check` et du demarrage (P7). Decide ici, une seule fois, pour l'instantane, config check, serve et le
# rechargement.

RELAY_UNAVAILABLE = "relay_unavailable"
"""Le relais natif lui-meme : leve au lot 4."""
AUTO_PENDING = "auto_pending"
"""Lot 4 (decision de l'auteur du 2026-11-13) : le relais natif etait un apercu jusqu'a la fin des lots du proxy - seule
`options.reverse_proxy.engine = native` l'activait ; `auto` gardait toutes les zones en Python. Leve au lot 11 : garde
pour les essais d'une configuration d'avant le lot 11."""
ZONE_BALANCING = "balancing"
"""Plusieurs backends, cookie collant, regles par en-tete, plafond de requetes du backend : lot 6."""
ZONE_DNS = "dns_name"
"""Backend designe par un nom DNS (resolution par Python a l'instantane, plusieurs adresses = plusieurs backends) :
lot 6, avec l'equilibrage."""
ZONE_CACHE = "cache"
"""Cache des reponses : reste en Python (Q6), jamais porte."""
ZONE_WEBSOCKET = "websocket"
"""WebSocket natif : lot 10 (fait). Garde pour les essais d'une configuration d'avant le lot 10."""
ZONE_UPSTREAM_TLS = "upstream_tls"
"""TLS vers le backend : lot 8 (fait)."""
ZONE_TLS_DIRECT = "tls_direct"
"""TLS direct pour une zone native : lot 9 (fait). Garde pour les essais d'une configuration d'avant le lot 9."""
ZONE_ENGINE_PYTHON = "engine_python"
"""options.reverse_proxy.engine = python : toutes les zones confiees, par choix."""

NATIVE_PROXY_GAPS: frozenset[str] = frozenset()
"""Ce que le relais natif ne sait pas encore faire : chaque lot a retire le sien (RELAY_UNAVAILABLE au lot 4,
ZONE_BALANCING et ZONE_DNS au lot 6, ZONE_UPSTREAM_TLS au lot 8, ZONE_TLS_DIRECT au lot 9, ZONE_WEBSOCKET au lot 10,
AUTO_PENDING au lot 11). Vide : avec `auto`, chaque zone est native, sauf le cache (toujours confie a Python, Q6)."""

_REMOVABLE_REASONS = (ZONE_CACHE, ZONE_WEBSOCKET, ZONE_UPSTREAM_TLS, ZONE_BALANCING, ZONE_DNS)
"""Raisons que l'utilisateur peut lever en retirant la fonction de la zone."""


@dataclass(frozen=True)
class ZoneEngine:
    url_prefix: str
    engine: str
    """« native » : relayee par le moteur natif ; « python » : connexion confiee a Python."""
    reasons: tuple[str, ...] = ()
    """Pourquoi la zone est confiee (vide pour une zone native)."""


def zone_engine_reasons(zone: ProxyZone, direct_tls: bool, gaps: frozenset[str] = NATIVE_PROXY_GAPS) -> tuple[str, ...]:
    reasons = []
    if RELAY_UNAVAILABLE in gaps:
        reasons.append(RELAY_UNAVAILABLE)
    if ZONE_BALANCING in gaps and (len(zone.upstreams) > 1 or zone.sticky_session_enabled or zone.routing_rules
                                   or any(u.max_concurrent_requests is not None for u in zone.upstreams)):
        reasons.append(ZONE_BALANCING)
    if ZONE_DNS in gaps and any(normalize_host_address(u.host) is None for u in zone.upstreams):
        reasons.append(ZONE_DNS)
    if zone.cache_enabled:
        reasons.append(ZONE_CACHE)
    if zone.websocket_enabled and ZONE_WEBSOCKET in gaps:
        reasons.append(ZONE_WEBSOCKET)
    if any(upstream.use_tls for upstream in zone.upstreams) and ZONE_UPSTREAM_TLS in gaps:
        reasons.append(ZONE_UPSTREAM_TLS)
    if direct_tls and ZONE_TLS_DIRECT in gaps:
        reasons.append(ZONE_TLS_DIRECT)
    return tuple(reasons)


def decide_proxy_zones(config: OmegaServConfig, gaps: frozenset[str] = NATIVE_PROXY_GAPS) -> tuple[ZoneEngine, ...]:
    """Choix par zone, a la construction de l'instantane (§5.2). Ne regarde pas `server.engine` : c'est le choix
    que ferait le moteur natif s'il tourne."""
    option = config.options.get("reverse_proxy")
    if option is None or not option.enabled:
        return ()
    settings = parse_proxy_engine_settings(option.settings)
    decisions = []
    for zone in parse_proxy_zones(option.settings.get("zones", [])):
        if settings.engine == "python":
            decisions.append(ZoneEngine(zone.url_prefix, "python", (ZONE_ENGINE_PYTHON,)))
            continue
        if settings.engine == "auto" and AUTO_PENDING in gaps:
            decisions.append(ZoneEngine(zone.url_prefix, "python", (AUTO_PENDING,)))
            continue
        reasons = zone_engine_reasons(zone, tls_direct(config), gaps)
        decisions.append(ZoneEngine(zone.url_prefix, "python" if reasons else "native", reasons))
    return tuple(decisions)


@dataclass(frozen=True)
class EngineProblem:
    """Erreur, avertissement ou avis de configuration : texte affiche (traduit) et texte d'error.log (francais fixe,
    comme le reste du journal d'erreurs)."""
    text: str
    log_text: str


@dataclass(frozen=True)
class EngineProblems:
    errors: tuple[EngineProblem, ...] = ()
    """Refus : config check, demarrage et rechargement (P7 : seulement reverse_proxy.engine = native)."""
    warnings: tuple[EngineProblem, ...] = ()
    """config check, et error.log au demarrage : jamais un refus, rien ne cesse de demarrer."""
    notices: tuple[EngineProblem, ...] = ()
    """config check seulement."""


def _reason_labels(reasons: tuple[str, ...]) -> tuple[str, str]:
    """Libelles (affiche, journal) des raisons qu'on peut lever en retirant une fonction de la zone."""
    display = {ZONE_CACHE: _("cache"), ZONE_WEBSOCKET: _("WebSocket"), ZONE_UPSTREAM_TLS: _("TLS vers le backend"),
               ZONE_BALANCING: _("plusieurs backends, cookie collant, règles par en-tête ou plafond de requêtes"),
               ZONE_DNS: _("nom DNS du backend (indiquer son adresse IP)")}
    log = {ZONE_CACHE: "cache", ZONE_WEBSOCKET: "WebSocket", ZONE_UPSTREAM_TLS: "TLS vers backend",  # error.log
           ZONE_BALANCING: "equilibrage", ZONE_DNS: "nom DNS"}
    kept = [reason for reason in reasons if reason in display]
    return ", ".join(display[r] for r in kept), ", ".join(log[r] for r in kept)


def proxy_engine_problems(config: OmegaServConfig, gaps: frozenset[str] = NATIVE_PROXY_GAPS) -> EngineProblems:
    """Regles P7 et P8 (tableau du §5.2)."""
    errors: list[EngineProblem] = []
    warnings: list[EngineProblem] = []
    notices: list[EngineProblem] = []
    direct = tls_direct(config)
    zones = decide_proxy_zones(config, gaps)
    if zones:
        engine = parse_proxy_engine_settings(config.options["reverse_proxy"].settings).engine
        delegated = [zone for zone in zones if zone.engine == "python"]
        if config.server.engine != "native":
            if engine == "native":  # decision de l'auteur du 2026-11-13 : ignore, le retour en arriere demarre
                notices.append(EngineProblem(
                    _("options.reverse_proxy.engine = native est sans effet avec server.engine = python : toutes "
                      "les zones sont relayées par le moteur Python"),
                    "options.reverse_proxy.engine = native sans effet (server.engine = python)"))
        elif engine == "native":
            for zone in delegated:
                # Message sans les raisons internes des lots a venir : seulement ce que l'utilisateur peut changer,
                # et seulement si le retirer suffit.
                shown, logged = _reason_labels(zone.reasons) if set(zone.reasons) <= set(_REMOVABLE_REASONS) else ("", "")
                fix = _(" (fonctions à retirer de la zone : {features})").format(features=shown) if shown else ""
                errors.append(EngineProblem(
                    _("options.reverse_proxy.engine = native : la zone {url_prefix!r} ne peut pas être relayée par le "
                      "moteur natif dans cette version{fix} - passer engine à auto pour la confier à Python").format(
                        url_prefix=zone.url_prefix, fix=fix),
                    f"options.reverse_proxy.engine = native : zone {zone.url_prefix!r} non relayable par le moteur "
                    f"natif" + (f" ({logged})" if logged else "")))
        elif direct and delegated:
            prefixes = ", ".join(repr(zone.url_prefix) for zone in delegated)
            removable = [zone for zone in delegated if zone.reasons and set(zone.reasons) <= set(_REMOVABLE_REASONS)]
            shown = "; ".join(f"{zone.url_prefix!r} : {_reason_labels(zone.reasons)[0]}" for zone in removable)
            other = _(", ou retirer de la zone ce que le moteur natif ne relaie pas ({details})").format(
                details=shown) if removable else ""
            warnings.append(EngineProblem(
                _("TLS en mode direct avec une zone du reverse proxy confiée à Python ({zones}) : le serveur démarre "
                  "avec le moteur Python. Pour garder le moteur natif : terminer TLS devant omega-serv "
                  "(tls.mode = behind_proxy){other}").format(zones=prefixes, other=other),
                f"TLS direct avec zone du reverse proxy confiee a Python ({prefixes}) : moteur Python utilise - "
                "pour garder le natif, terminer TLS en amont (tls.mode = behind_proxy)"))
    if config.server.engine == "native" and direct:
        for option, label in (("fastcgi", "FastCGI"), ("upload", _("envoi de fichiers"))):
            if config.option_enabled(option):
                warnings.append(EngineProblem(
                    _("TLS en mode direct avec {feature} : ces routes sont servies par le moteur Python, le serveur "
                      "démarre donc avec le moteur Python. Pour garder le moteur natif : terminer TLS devant "
                      "omega-serv (tls.mode = behind_proxy)").format(feature=label),
                    f"TLS direct avec options.{option} : moteur Python utilise - pour garder le natif, terminer TLS "
                    "en amont (tls.mode = behind_proxy)"))
    return EngineProblems(tuple(errors), tuple(warnings), tuple(notices))


def decide_engine(config: OmegaServConfig, binary_problem: str | None) -> EngineDecision:
    """`binary_problem` : None si le binaire natif est present et executable, sinon BINARY_MISSING /
    BINARY_NOT_EXECUTABLE (verifie par l'infrastructure, jamais suppose ici)."""
    requested = config.server.engine
    if requested != "native":
        return EngineDecision(requested, "python")
    reasons = ([binary_problem] if binary_problem else []) + native_unsupported_features(config)
    notices: tuple[str, ...] = ()  # lot 7 : server.workers = processus de securite du natif, jamais ignore
    if reasons:
        return EngineDecision(requested, "python", tuple(reasons), notices)
    return EngineDecision(requested, "native", (), notices)


_OPTION_LABELS = {
    "waf": "WAF",
    "auth": "Auth",
    "active_defense": "Active Defense",
    "upload": "Upload",
    "fastcgi": "FastCGI / PHP",
    "reverse_proxy": "Reverse proxy",
    "dirlisting": "Dirlisting",
}


def describe_reason(code: str) -> str:
    """Texte affiche (TUI, `engine status`) : quoi, et comment lever la cause."""
    if code == BINARY_MISSING:
        return _("binaire natif absent ({path}) - réinstaller l'archive complète").format(path=NATIVE_BINARY_RELATIVE_PATH)
    if code == BINARY_NOT_EXECUTABLE:
        return _("binaire natif non exécutable ({path})").format(path=NATIVE_BINARY_RELATIVE_PATH)
    if code == TLS_HANDOFF:
        return _("TLS en mode direct avec une zone de reverse proxy confiée à Python (cache), FastCGI ou envoi de "
                 "fichiers : ces routes demandent de confier la connexion à Python, impossible quand le moteur natif "
                 "chiffre lui-même - passer en mode behind_proxy, ou retirer ces fonctions")
    if code == WORKERS_IGNORED:
        return _("le nombre de workers (mode boost) ne s'applique pas au moteur natif, qui utilise ses propres fils")
    if code in _OPTION_LABELS:
        return _("option {option} active : pas encore prise en charge par le moteur natif - la désactiver "
                 "pour utiliser le natif").format(option=_OPTION_LABELS[code])
    return _("raison inconnue : {code}").format(code=code)


def log_reason(code: str) -> str:
    """Texte d'error.log (francais fixe, comme le reste du journal d'erreurs)."""
    if code == BINARY_MISSING:
        return f"binaire natif absent ({NATIVE_BINARY_RELATIVE_PATH})"
    if code == BINARY_NOT_EXECUTABLE:
        return f"binaire natif non executable ({NATIVE_BINARY_RELATIVE_PATH})"
    if code == TLS_HANDOFF:
        return "TLS direct avec route applicative (connexion non transmissible a Python)"
    if code in _OPTION_LABELS:
        return f"option {code} active, non prise en charge par le moteur natif"
    return code


_NATIVE_ZONES_CACHE: list = [None, frozenset()]


def native_zone_prefixes(config: OmegaServConfig) -> frozenset[str]:
    """Plan proxy natif v2, lot 6 (P6) : prefixes des zones que le moteur natif relaie lui-meme - leurs sondes et leur
    sante appartiennent au natif et au processus de securite n° 0. Memorise pour la derniere configuration vue
    (appele a chaque resultat de sonde)."""
    if _NATIVE_ZONES_CACHE[0] is not config:
        _NATIVE_ZONES_CACHE[0] = config
        _NATIVE_ZONES_CACHE[1] = frozenset(z.url_prefix for z in decide_proxy_zones(config) if z.engine == "native")
    return cast("frozenset[str]", _NATIVE_ZONES_CACHE[1])
