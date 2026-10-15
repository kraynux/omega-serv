"""Detection de conflits de configuration (spec §6.4).

Distinct de validation.py (structurel : est-ce que CETTE config seule
est bien formee) : ici, on detecte des incoherences entre options et
reste de la configuration. Perimetre volontairement restreint a ce qui
est reellement verifiable maintenant - WAF (Phase 5), auth (Phase 7),
dirlisting (Phase 4) et TLS/HSTS (Phase 6) n'existent pas encore comme
champs de configuration concrets : leurs conflits d'exemple dans la
spec (§6.4) seront ajoutes ici au fur et a mesure que ces phases
introduisent les champs correspondants, jamais anticipes a vide.

Chevauchement de prefixe entre types de zones (OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §29.4/§30.1, construit comme item 2 de l'ordre de
construction §26, juste apres la Phase 5) : angle mort preexistant
confirme par audit - `validate_config` (validation.py) ne detecte
aujourd'hui qu'un chevauchement UPSTREAM-vs-UPSTREAM au sein du reverse
proxy (boucle de proxy), jamais un chevauchement de PREFIXE entre deux
TYPES de zones differents (ex. un alias et une zone reverse-proxy qui
partagent le meme prefixe) - le pipeline de dispatch
(application/server/route_request.py) tranche alors silencieusement
selon l'ORDRE D'EVALUATION des etapes, jamais signale a l'utilisateur.
Volontairement une `severity="warning"` (jamais `"error"`) : un
chevauchement peut etre parfaitement voulu (ex. un alias plus specifique
cense "percer" une zone plus generale) - seulement signaler, jamais
bloquer la sauvegarde d'une configuration par ailleurs valide."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.alias import parse_alias_rules
from omega_serv.domain.routing.fastcgi_zone import parse_fastcgi_config
from omega_serv.domain.routing.proxy_zone import parse_proxy_zones
from omega_serv.domain.routing.redirect import parse_redirect_rules
from omega_serv.domain.routing.upload_zone import parse_upload_zone_rules
from omega_serv.domain.routing.zone_resolver import path_matches_prefix

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class ConfigConflict:
    severity: Severity
    message: str


_ZONE_DISPATCH_ORDER = ("redirects", "alias", "upload", "fastcgi", "reverse_proxy")
"""Ordre REEL du pipeline de dispatch entre types de zones mutuellement
exclusifs (application/server/route_request.py, verifie par lecture du
code) : le premier type de cette liste a correspondre a un chemin donne
l'emporte TOUJOURS, quelle que soit la longueur relative des prefixes -
contrairement a `resolve_zone()` au sein d'un MEME type de zone, qui
applique plus-long-prefixe-gagne. `rewrites` est absent (pas de notion
de prefixe de zone - transforme le chemin pour tout le monde, ne
"gagne" jamais une requete) ; `access_control`/`auth`/`csp_zones` sont
absents aussi - ils se superposent a la zone qui traite la requete,
ils ne se substituent jamais a elle (§29.4/§29.7)."""


def _collect_dispatch_zone_prefixes(config: OmegaServConfig) -> list[tuple[str, str]]:
    """Retourne (type, url_prefix) pour chaque zone d'un type present
    dans `_ZONE_DISPATCH_ORDER`, uniquement pour les options activees."""
    prefixes: list[tuple[str, str]] = []

    aliases_option = config.options.get("aliases")
    if aliases_option is not None and aliases_option.enabled:
        prefixes.extend(("alias", rule.url_prefix) for rule in parse_alias_rules(aliases_option.settings.get("list", [])))

    redirects_option = config.options.get("redirects")
    if redirects_option is not None and redirects_option.enabled:
        prefixes.extend(
            ("redirects", rule.url_prefix) for rule in parse_redirect_rules(redirects_option.settings.get("list", []))
        )

    upload_option = config.options.get("upload")
    if upload_option is not None and upload_option.enabled:
        prefixes.extend(
            ("upload", rule.url_prefix) for rule in parse_upload_zone_rules(upload_option.settings.get("zones", []))
        )

    fastcgi_option = config.options.get("fastcgi")
    if fastcgi_option is not None and fastcgi_option.enabled:
        prefixes.append(("fastcgi", parse_fastcgi_config(fastcgi_option.settings).url_prefix))

    reverse_proxy_option = config.options.get("reverse_proxy")
    if reverse_proxy_option is not None and reverse_proxy_option.enabled:
        prefixes.extend(
            ("reverse_proxy", zone.url_prefix) for zone in parse_proxy_zones(reverse_proxy_option.settings.get("zones", []))
        )

    return prefixes


def detect_zone_prefix_overlaps(config: OmegaServConfig) -> list[ConfigConflict]:
    conflicts: list[ConfigConflict] = []
    prefixes = _collect_dispatch_zone_prefixes(config)
    for i, (type_a, prefix_a) in enumerate(prefixes):
        for type_b, prefix_b in prefixes[i + 1:]:
            if type_a == type_b:
                continue
            if not (path_matches_prefix(prefix_a, prefix_b) or path_matches_prefix(prefix_b, prefix_a)):
                continue
            rank_a, rank_b = _ZONE_DISPATCH_ORDER.index(type_a), _ZONE_DISPATCH_ORDER.index(type_b)
            winner_type, winner_prefix = (type_a, prefix_a) if rank_a < rank_b else (type_b, prefix_b)
            loser_type, loser_prefix = (type_b, prefix_b) if rank_a < rank_b else (type_a, prefix_a)
            conflicts.append(ConfigConflict(
                "warning",
                f"chevauchement de prefixe entre options.{type_a} ({prefix_a!r}) et options.{type_b} "
                f"({prefix_b!r}) : options.{winner_type} ({winner_prefix!r}) l'emporte toujours pour "
                f"les chemins correspondant aux deux (ordre du pipeline de dispatch, pas le prefixe "
                f"le plus long) - options.{loser_type} ({loser_prefix!r}) restera inatteignable pour "
                "ces chemins (plan reverse proxy §29.4/§30.1)",
            ))
    return conflicts


def detect_conflicts(config: OmegaServConfig) -> list[ConfigConflict]:
    conflicts: list[ConfigConflict] = []

    trusted_proxy = config.options.get("trusted_proxy")
    if trusted_proxy is not None and trusted_proxy.enabled:
        networks = trusted_proxy.settings.get("trusted_networks")
        if not networks:
            conflicts.append(ConfigConflict(
                "error",
                "trusted_proxy.enabled=true sans trusted_networks defini (spec §6.4, §19.3)",
            ))

    conflicts.extend(detect_zone_prefix_overlaps(config))

    return conflicts


def has_blocking_conflicts(conflicts: list[ConfigConflict]) -> bool:
    return any(c.severity == "error" for c in conflicts)
