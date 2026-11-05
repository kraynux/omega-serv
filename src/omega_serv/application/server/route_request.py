"""Pipeline de routage (spec §27) : redirections, reecritures, alias,
FastCGI, puis fichier statique/listing de repertoire - dans cet ordre.
WAF/Auth (Phases 5/7) restent des verifications faites en amont, dans
infrastructure/server/asyncio_server.py, avant meme d'appeler cette
fonction - pas des etapes de ce pipeline de routage lui-meme.

Chaque etape reste desactivable independamment (option enabled=false)
et n'affecte jamais les autres - toujours conforme au modele
"profil + options superposables".

`async def` depuis la Phase 8 : la communication FastCGI est reseau
(socket Unix), jamais bloquante pour le reste du serveur."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.application.server.healthz import HEALTHZ_PATH, handle_healthz
from omega_serv.application.server.proxy_cache_locks import ProxyCacheLocks
from omega_serv.application.server.serve_dirlisting_css import (
    CSS_URL_PREFIX,
    handle_dirlisting_css_request,
)
from omega_serv.application.server.serve_error_css import (
    ERROR_CSS_URL_PREFIX,
    handle_error_css_request,
)
from omega_serv.application.server.serve_fastcgi import serve_fastcgi
from omega_serv.application.server.serve_icon import ICON_URL_PREFIX, handle_icon_request
from omega_serv.application.server.serve_proxy import serve_proxy
from omega_serv.application.server.serve_proxy_admin import ADMIN_URL_PREFIX, handle_admin_request
from omega_serv.application.server.serve_proxy_load import LOAD_URL_PREFIX, handle_load_request
from omega_serv.application.server.serve_static_file import serve_static_file
from omega_serv.application.upload.handle_upload import handle_upload
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.access_rule import (
    AccessRule,
    has_explicit_allow_match,
    parse_access_rules,
)
from omega_serv.domain.routing.alias import AliasRule, parse_alias_rules
from omega_serv.domain.routing.cache_policy import CachePolicy, parse_cache_policy
from omega_serv.domain.routing.dirlisting import DirlistingSettings
from omega_serv.domain.routing.fastcgi_zone import FastCgiConfig, parse_fastcgi_config
from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    ProxyLoadBalancerState,
    ProxyZone,
    parse_proxy_zones,
    resolve_proxy_zone,
)
from omega_serv.domain.routing.redirect import RedirectRule, parse_redirect_rules
from omega_serv.domain.routing.rewrite import RewriteRule, apply_rewrites, parse_rewrite_rules
from omega_serv.domain.routing.upload_zone import UploadZoneRule, parse_upload_zone_rules
from omega_serv.domain.routing.zone_resolver import Zone, path_matches_prefix, resolve_zone
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.infrastructure.upload.filesystem_upload_storage import FilesystemUploadStorage
from omega_serv.ports.fastcgi_client_port import FastCgiClientPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort
from omega_serv.ports.logger_port import LoggerPort
from omega_serv.ports.proxy_cache_store_port import ProxyCacheStorePort


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
    return DirlistingSettings.from_dict(settings)


def _cache_policy(config: OmegaServConfig) -> CachePolicy | None:
    settings = _option_settings(config, "cache")
    if settings is None:
        return None
    return parse_cache_policy(settings)


def _upload_zones(config: OmegaServConfig) -> tuple[Zone[UploadZoneRule], ...]:
    settings = _option_settings(config, "upload")
    if settings is None:
        return ()
    return tuple(Zone(rule.url_prefix, rule) for rule in parse_upload_zone_rules(settings.get("zones", [])))


def _access_control_override(tables: RoutingTables, path: str) -> bool:
    if tables.access_rules is None:
        return False
    return has_explicit_allow_match(path, list(tables.access_rules))


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
    fastcgi_config: FastCgiConfig | None
    proxy_zones: tuple[ProxyZone, ...] | None
    access_rules: tuple[AccessRule, ...] | None


def build_routing_tables(config: OmegaServConfig) -> RoutingTables:
    trusted_proxy_settings = _option_settings(config, "trusted_proxy")
    redirect_settings = _option_settings(config, "redirects")
    rewrite_settings = _option_settings(config, "rewrites")
    alias_settings = _option_settings(config, "aliases")
    fastcgi_settings = _option_settings(config, "fastcgi")
    proxy_settings = _option_settings(config, "reverse_proxy")
    access_settings = _option_settings(config, "access_control")
    return RoutingTables(
        trusted_networks=tuple(trusted_proxy_settings.get("trusted_networks", [])) if trusted_proxy_settings else (),
        redirect_zones=None if redirect_settings is None else tuple(
            Zone(rule.url_prefix, rule) for rule in parse_redirect_rules(redirect_settings.get("list", []))
        ),
        rewrite_rules=None if rewrite_settings is None else tuple(parse_rewrite_rules(rewrite_settings.get("list", []))),
        alias_zones=None if alias_settings is None else tuple(
            Zone(rule.url_prefix, rule) for rule in parse_alias_rules(alias_settings.get("list", []))
        ),
        dirlisting_zones=_dirlisting_zones(config),
        dirlisting_settings=_dirlisting_settings(config),
        cache_policy=_cache_policy(config),
        upload_zones=_upload_zones(config),
        fastcgi_config=None if fastcgi_settings is None else parse_fastcgi_config(fastcgi_settings),
        proxy_zones=None if proxy_settings is None else tuple(parse_proxy_zones(proxy_settings.get("zones", []))),
        access_rules=None if access_settings is None else tuple(parse_access_rules(access_settings.get("list", []))),
    )


_tables_cache: tuple[OmegaServConfig, RoutingTables] | None = None


def routing_tables(config: OmegaServConfig) -> RoutingTables:
    """Tables de `config`, construites a sa premiere requete. Comparaison par IDENTITE (`is`) et reference
    forte gardee : un objet recycle ne peut jamais etre confondu avec l'ancienne configuration."""
    global _tables_cache
    if _tables_cache is None or _tables_cache[0] is not config:
        _tables_cache = (config, build_routing_tables(config))
    return _tables_cache[1]


async def route_request(
    request: HttpRequest,
    path_resolver: SafePathResolver,
    filesystem: FilesystemPort,
    config: OmegaServConfig,
    project_root: Path,
    fastcgi_client: FastCgiClientPort | None = None,
    logger: LoggerPort | None = None,
    proxy_client: HttpProxyClientPort | None = None,
    proxy_load_balancer: ProxyLoadBalancerState | None = None,
    proxy_health_state: ProxyHealthState | None = None,
    proxy_client_ssl_context_verified: ssl.SSLContext | None = None,
    proxy_client_ssl_context_unverified: ssl.SSLContext | None = None,
    proxy_cache_store: ProxyCacheStorePort | None = None,
    proxy_cache_locks: ProxyCacheLocks | None = None,
    proxy_cache_metrics: ProxyCacheMetrics | None = None,
) -> HttpResponse:
    if request.path == HEALTHZ_PATH:
        return handle_healthz(request)

    if request.path.startswith(ICON_URL_PREFIX):
        return handle_icon_request(request)

    if request.path.startswith(CSS_URL_PREFIX):
        return handle_dirlisting_css_request(request)

    if request.path.startswith(ERROR_CSS_URL_PREFIX):
        return handle_error_css_request(request)

    tables = routing_tables(config)

    if request.path.startswith(LOAD_URL_PREFIX):
        return handle_load_request(request, list(tables.trusted_networks))

    if request.path.startswith(ADMIN_URL_PREFIX):
        if proxy_health_state is None or proxy_cache_metrics is None:
            return HttpResponse.empty(HttpStatus.NOT_FOUND)
        return handle_admin_request(request, list(tables.trusted_networks), config, proxy_health_state, proxy_cache_metrics)

    if tables.redirect_zones is not None:
        matched_redirect = resolve_zone(request.path, list(tables.redirect_zones))
        if matched_redirect is not None:
            response = HttpResponse.empty(HttpStatus(matched_redirect.data.status_code))
            response.set_header("Location", matched_redirect.data.destination)
            return response

    effective_path = request.path
    if tables.rewrite_rules is not None:
        result = apply_rewrites(effective_path, list(tables.rewrite_rules))
        if result.loop_detected:
            return HttpResponse.empty(HttpStatus.INTERNAL_SERVER_ERROR)
        effective_path = result.final_path

    effective_request = request if effective_path == request.path else replace(request, path=effective_path)

    dirlisting_zones = tables.dirlisting_zones
    dirlisting_settings = tables.dirlisting_settings
    cache_policy = tables.cache_policy

    if tables.alias_zones is not None:
        matched_alias = resolve_zone(effective_path, list(tables.alias_zones))
        if matched_alias is not None:
            alias_rule = matched_alias.data
            remaining = effective_path[len(alias_rule.url_prefix):].lstrip("/")
            alias_request = replace(effective_request, path="/" + remaining)
            alias_resolver = SafePathResolver(filesystem, project_root / alias_rule.target_path)
            return serve_static_file(
                alias_request, alias_resolver, filesystem, config.security, config.server.index_files,
                dirlisting_zones=dirlisting_zones, dirlisting_settings=dirlisting_settings,
                cache_policy=cache_policy,
                access_control_override=_access_control_override(tables, effective_path),
                display_path=effective_path,
            )

    if request.method == "POST":
        matched_upload = resolve_zone(effective_path, list(tables.upload_zones))
        if matched_upload is not None:
            storage = FilesystemUploadStorage(filesystem, project_root)
            return handle_upload(
                effective_request, matched_upload, request.body or b"", storage, SystemClock(),
                logger=logger, upload_log_path=project_root / config.logs.uploads,
            )

    fastcgi_config = tables.fastcgi_config
    if (
        fastcgi_config is not None and fastcgi_client is not None
        and path_matches_prefix(effective_path, fastcgi_config.url_prefix)
    ):
        fastcgi_resolver = SafePathResolver(filesystem, project_root / fastcgi_config.script_root)
        return await serve_fastcgi(
            effective_request, fastcgi_config, fastcgi_resolver, filesystem, fastcgi_client, project_root,
            config.server.server_name or config.server.bind, config.server.port,
        )

    if (
        tables.proxy_zones is not None and proxy_client is not None and proxy_load_balancer is not None
        and proxy_health_state is not None
    ):
        matched_proxy_zone = resolve_proxy_zone(effective_path, list(tables.proxy_zones))
        if matched_proxy_zone is not None:
            return await serve_proxy(
                effective_request, matched_proxy_zone, proxy_client, proxy_load_balancer, proxy_health_state,
                proxy_client_ssl_context_verified, proxy_client_ssl_context_unverified,
                proxy_cache_store, proxy_cache_locks, proxy_cache_metrics,
            )

    return serve_static_file(
        effective_request, path_resolver, filesystem, config.security, config.server.index_files,
        dirlisting_zones=dirlisting_zones, dirlisting_settings=dirlisting_settings,
        cache_policy=cache_policy,
        access_control_override=_access_control_override(tables, effective_path),
    )
