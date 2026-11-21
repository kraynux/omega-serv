"""Tables de routage (redirections, reecritures, alias, listing, cache, envoi de fichiers, FastCGI, reverse proxy,
controle d'acces), analysees UNE fois par configuration - plan moteur C++, lot 0 (2026-11-02).

Separees du pipeline de routage (route_request.py) le 2026-11-19 (passe memoire, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md
§7) : le superviseur du moteur natif construit l'instantane de configuration avec ces tables sans charger le code
qui sert les requetes. Construire les tables charge aussi le code de service des options actives (et seulement
d'elles) : `build_routing_tables` est appelee au demarrage et a chaque rechargement (option_code.py), jamais un
import disque pendant une requete."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.access_rule import AccessRule, parse_access_rules
from omega_serv.domain.routing.proxy_zone import (
    DEFAULT_MAX_RESPONSE_BODY_MB,
    ProxyZone,
    parse_proxy_zones,
    resolve_proxy_zone,
)
from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone
from omega_serv.domain.security.path_policy import canonical_path

if TYPE_CHECKING:
    from omega_serv.domain.routing.alias import AliasRule
    from omega_serv.domain.routing.cache_policy import CachePolicy
    from omega_serv.domain.routing.dirlisting import DirlistingSettings
    from omega_serv.domain.routing.fastcgi_zone import FastCgiConfig
    from omega_serv.domain.routing.redirect import RedirectRule
    from omega_serv.domain.routing.rewrite import RewriteRule
    from omega_serv.domain.routing.upload_zone import UploadZoneRule


def _load_option_code(*modules: str) -> None:
    """Charge le code de service d'une option active pendant la construction des tables (demarrage, rechargement) :
    route_request l'importe ensuite localement sans jamais lire le disque pendant une requete."""
    for module in modules:
        importlib.import_module(module)


def _option_settings(config: OmegaServConfig, name: str) -> dict | None:
    option = config.options.get(name)
    if option is None or not option.enabled:
        return None
    return option.settings


def _dirlisting_zones(config: OmegaServConfig) -> tuple[Zone[bool], ...]:
    settings = _option_settings(config, "dirlisting")
    if settings is None:
        return ()
    return tuple(Zone(prefix, True) for prefix in settings.get("zone_prefixes", []))


def _dirlisting_settings(config: OmegaServConfig) -> DirlistingSettings | None:
    settings = _option_settings(config, "dirlisting")
    if settings is None:
        return None
    from omega_serv.domain.routing.dirlisting import DirlistingSettings
    return DirlistingSettings.from_dict(settings)


def _cache_policy(config: OmegaServConfig) -> CachePolicy | None:
    settings = _option_settings(config, "cache")
    if settings is None:
        return None
    from omega_serv.domain.routing.cache_policy import parse_cache_policy
    return parse_cache_policy(settings)


def _upload_zones(config: OmegaServConfig) -> tuple[Zone[UploadZoneRule], ...]:
    settings = _option_settings(config, "upload")
    if settings is None:
        return ()
    _load_option_code("omega_serv.application.upload.handle_upload",
                      "omega_serv.infrastructure.upload.filesystem_upload_storage")
    from omega_serv.domain.routing.upload_zone import parse_upload_zone_rules
    return tuple(Zone(rule.url_prefix, rule) for rule in parse_upload_zone_rules(settings.get("zones", [])))


@dataclass(frozen=True)
class RoutingTables:
    """Regles de routage analysees UNE fois par configuration (plan moteur C++, lot 0, 2026-11-02 : elles
    etaient re-analysees a chaque requete). Le serveur remplace l'objet de configuration a chaque
    rechargement : une nouvelle configuration donne toujours de nouvelles tables, jamais des tables perimees."""
    trusted_networks: tuple[str, ...]
    redirect_zones: tuple[Zone[RedirectRule], ...] | None
    rewrite_rules: tuple[RewriteRule, ...] | None
    alias_zones: tuple[Zone[AliasRule], ...] | None
    dirlisting_zones: tuple[Zone[bool], ...]
    dirlisting_settings: DirlistingSettings | None
    cache_policy: CachePolicy | None
    upload_zones: tuple[Zone[UploadZoneRule], ...]
    # Projets 3.0.0 §8.1 : une zone par prefixe (le plus long l'emporte), zones arretees comprises (503).
    fastcgi_zones: tuple[Zone[FastCgiConfig], ...]
    proxy_zones: tuple[ProxyZone, ...] | None
    access_rules: tuple[AccessRule, ...] | None
    # Plan proxy natif v2, lot 1 (D23) : options.reverse_proxy.max_response_body_mb, en octets.
    proxy_max_response_body_bytes: int = DEFAULT_MAX_RESPONSE_BODY_MB * 1024 * 1024


def build_routing_tables(config: OmegaServConfig) -> RoutingTables:
    trusted_proxy_settings = _option_settings(config, "trusted_proxy")
    redirect_settings = _option_settings(config, "redirects")
    rewrite_settings = _option_settings(config, "rewrites")
    alias_settings = _option_settings(config, "aliases")
    fastcgi_settings = _option_settings(config, "fastcgi")
    proxy_settings = _option_settings(config, "reverse_proxy")
    access_settings = _option_settings(config, "access_control")
    if trusted_proxy_settings and trusted_proxy_settings.get("trusted_networks"):
        _load_option_code("omega_serv.infrastructure.probe.system_stats")  # route /.omega-serv-load/
    redirect_zones: tuple[Zone[RedirectRule], ...] | None = None
    if redirect_settings is not None:
        from omega_serv.domain.routing.redirect import parse_redirect_rules
        redirect_zones = tuple(Zone(rule.url_prefix, rule) for rule in parse_redirect_rules(redirect_settings.get("list", [])))
    rewrite_rules: tuple[RewriteRule, ...] | None = None
    if rewrite_settings is not None:
        from omega_serv.domain.routing.rewrite import parse_rewrite_rules
        rewrite_rules = tuple(parse_rewrite_rules(rewrite_settings.get("list", [])))
    alias_zones: tuple[Zone[AliasRule], ...] | None = None
    if alias_settings is not None:
        from omega_serv.domain.routing.alias import parse_alias_rules
        alias_zones = tuple(Zone(rule.url_prefix, rule) for rule in parse_alias_rules(alias_settings.get("list", [])))
    fastcgi_zones: tuple[Zone[FastCgiConfig], ...] = ()
    if fastcgi_settings is not None:
        _load_option_code("omega_serv.application.server.serve_fastcgi")
        from omega_serv.domain.routing.fastcgi_zone import parse_fastcgi_zones
        fastcgi_zones = tuple(Zone(zone.url_prefix, zone) for zone in parse_fastcgi_zones(fastcgi_settings))
    proxy_zones: tuple[ProxyZone, ...] | None = None
    if proxy_settings is not None:
        _load_option_code("omega_serv.application.server.serve_proxy")
        proxy_zones = tuple(parse_proxy_zones(proxy_settings.get("zones", [])))
    return RoutingTables(
        trusted_networks=tuple(trusted_proxy_settings.get("trusted_networks", [])) if trusted_proxy_settings else (),
        redirect_zones=redirect_zones,
        rewrite_rules=rewrite_rules,
        alias_zones=alias_zones,
        dirlisting_zones=_dirlisting_zones(config),
        dirlisting_settings=_dirlisting_settings(config),
        cache_policy=_cache_policy(config),
        upload_zones=_upload_zones(config),
        fastcgi_zones=fastcgi_zones,
        proxy_zones=proxy_zones,
        access_rules=None if access_settings is None else tuple(parse_access_rules(access_settings.get("list", []))),
        proxy_max_response_body_bytes=int(
            (proxy_settings or {}).get("max_response_body_mb", DEFAULT_MAX_RESPONSE_BODY_MB)) * 1024 * 1024,
    )


_tables_cache: tuple[OmegaServConfig, RoutingTables] | None = None


def routing_tables(config: OmegaServConfig) -> RoutingTables:
    """Tables de `config`, construites a sa premiere requete. Comparaison par IDENTITE (`is`) et reference
    forte gardee : un objet recycle ne peut jamais etre confondu avec l'ancienne configuration."""
    global _tables_cache
    if _tables_cache is None or _tables_cache[0] is not config:
        _tables_cache = (config, build_routing_tables(config))
    return _tables_cache[1]


def effective_request_path(config: OmegaServConfig, path: str) -> str | None:
    """Chemin apres les reecritures (None : boucle de reecriture). Plan proxy natif v2, lot 1 (D14) : partage avec
    le raccourci WebSocket, qui choisissait sa zone sur le chemin brut alors que le routage suit les reecritures."""
    tables = routing_tables(config)
    if tables.rewrite_rules is None:
        return path
    from omega_serv.domain.routing.rewrite import apply_rewrites
    result = apply_rewrites(path, list(tables.rewrite_rules))
    return None if result.loop_detected else result.final_path


def requires_full_body(config: OmegaServConfig, path: str) -> bool:
    """Plan proxy natif v2, lot 1 (D34, P9) : la requete part-elle vers une route qui transmet son corps (zone
    proxy, FastCGI, envoi de fichiers) ? Seules ces routes lisent le corps entier ; les autres s'en tiennent a
    `waf.inspect.body_max_inspect_bytes`, comme le natif. Avant : activer l'une de ces options faisait lire et
    inspecter le corps entier sur TOUTES les routes (lien cache entre options, C20)."""
    tables = routing_tables(config)
    effective_path = canonical_path(effective_request_path(config, path) or path) or path
    matched_fastcgi = resolve_zone(effective_path, list(tables.fastcgi_zones))
    if matched_fastcgi is not None and matched_fastcgi.data.enabled:
        return True
    if resolve_zone(effective_path, list(tables.upload_zones)) is not None:
        return True
    return tables.proxy_zones is not None and resolve_proxy_zone(effective_path, list(tables.proxy_zones)) is not None


def request_size_limit(config: OmegaServConfig, path: str) -> int:
    """Projets 3.0.0 §9 (decision de l'auteur du 2026-11-16) : taille maximale du corps pour cette requete. Une zone
    FastCGI active qui fixe sa propre taille l'emporte ; sinon la taille globale (ecran Limites). Les deux moteurs
    passent par ici : le natif confie toute requete FastCGI a Python avant de lire le corps."""
    if config.option_enabled("fastcgi"):
        effective_path = canonical_path(effective_request_path(config, path) or path) or path
        matched = resolve_zone(effective_path, list(routing_tables(config).fastcgi_zones))
        if matched is not None and matched.data.enabled and matched.data.max_request_size is not None:
            return int(matched.data.max_request_size)
    return config.server.max_request_size
