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

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from omega_serv.application.server.healthz import HEALTHZ_PATH, handle_healthz
from omega_serv.application.server.routing_tables import (
    RoutingTables,
    effective_request_path,
    routing_tables,
)
from omega_serv.application.server.serve_dirlisting_css import (
    CSS_URL_PREFIX,
    handle_dirlisting_css_request,
)
from omega_serv.application.server.serve_error_css import (
    ERROR_CSS_URL_PREFIX,
    handle_error_css_request,
)
from omega_serv.application.server.serve_icon import ICON_URL_PREFIX, handle_icon_request
from omega_serv.application.server.serve_proxy_admin import ADMIN_URL_PREFIX, handle_admin_request
from omega_serv.application.server.serve_proxy_load import LOAD_URL_PREFIX, handle_load_request
from omega_serv.application.server.serve_static_file import serve_static_file
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.logging.error_log_line import format_error_log_line
from omega_serv.domain.routing.access_rule import has_explicit_allow_match
from omega_serv.domain.routing.proxy_zone import resolve_proxy_zone
from omega_serv.domain.routing.zone_resolver import resolve_zone
from omega_serv.domain.security.path_policy import canonical_path, normalize_uri_path
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver

if TYPE_CHECKING:
    import ssl

    from omega_serv.application.server.proxy_cache_locks import ProxyCacheLocks
    from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
    from omega_serv.domain.routing.proxy_health import ProxyHealthState
    from omega_serv.domain.routing.proxy_zone import ProxyLoadBalancerState
    from omega_serv.ports.fastcgi_client_port import FastCgiClientPort
    from omega_serv.ports.filesystem_port import FilesystemPort
    from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort
    from omega_serv.ports.logger_port import LoggerPort
    from omega_serv.ports.proxy_cache_store_port import ProxyCacheStorePort


def _access_control_override(tables: RoutingTables, path: str) -> bool:
    if tables.access_rules is None:
        return False
    return has_explicit_allow_match(path, list(tables.access_rules))


def _error_logger(
    logger: LoggerPort | None, project_root: Path, config: OmegaServConfig, request_id: str,
) -> Callable[[str], None] | None:
    """Lot 1 (D23) : ligne d'error.log au format du serveur, pour une erreur decidee pendant le routage."""
    if logger is None:
        return None

    def log(message: str) -> None:
        logger.append_line(project_root / config.logs.error,
                           format_error_log_line(datetime.now(timezone.utc), message, request_id))

    return log


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
        return handle_admin_request(request, list(tables.trusted_networks), config, proxy_health_state,
                                    proxy_cache_metrics, proxy_load_balancer)

    if tables.redirect_zones is not None:
        matched_redirect = resolve_zone(request.path, list(tables.redirect_zones))
        if matched_redirect is not None:
            response = HttpResponse.empty(HttpStatus(matched_redirect.data.status_code))
            response.set_header("Location", matched_redirect.data.destination)
            return response

    effective_path = effective_request_path(config, request.path)
    if effective_path is None:
        return HttpResponse.empty(HttpStatus.INTERNAL_SERVER_ERROR)

    effective_request = request if effective_path == request.path else replace(request, path=effective_path)
    # Scan de securite n° 1 (2026-11-20, cause A) : les zones (alias, envoi, FastCGI, proxy) et la regle `allow`
    # se choisissent sur le chemin canonique, le meme que celui des zones d'authentification et des regles d'acces.
    # Le chemin recu reste celui transmis au backend ou au script.
    match_path = canonical_path(effective_path)
    if match_path is None:  # 403 pour un `..` qui sortirait de la racine, 400 sinon (comme le resolveur)
        return HttpResponse.empty(normalize_uri_path(effective_path).suggested_status or HttpStatus.BAD_REQUEST)

    dirlisting_zones = tables.dirlisting_zones
    dirlisting_settings = tables.dirlisting_settings
    cache_policy = tables.cache_policy

    if tables.alias_zones is not None:
        matched_alias = resolve_zone(match_path, list(tables.alias_zones))
        if matched_alias is not None:
            alias_rule = matched_alias.data
            remaining = match_path[len(alias_rule.url_prefix.rstrip("/")):].lstrip("/")
            # Le resolveur decode encore deux fois : chaque `%` du reste canonique lui est rendu encode deux fois,
            # pour qu'il retrouve exactement ce chemin (un `%` litteral ne redevient jamais un separateur ou `..`).
            alias_request = replace(effective_request, path="/" + remaining.replace("%", "%2525"))
            alias_resolver = SafePathResolver(filesystem, project_root / alias_rule.target_path)
            return serve_static_file(
                alias_request, alias_resolver, filesystem, config.security, config.server.index_files,
                dirlisting_zones=dirlisting_zones, dirlisting_settings=dirlisting_settings,
                cache_policy=cache_policy,
                access_control_override=_access_control_override(tables, match_path),
                display_path=effective_path,
            )

    if request.method == "POST":
        matched_upload = resolve_zone(match_path, list(tables.upload_zones))
        if matched_upload is not None:
            from omega_serv.application.upload.handle_upload import handle_upload
            from omega_serv.infrastructure.clock.system_clock import SystemClock
            from omega_serv.infrastructure.upload.filesystem_upload_storage import (
                FilesystemUploadStorage,
            )
            storage = FilesystemUploadStorage(filesystem, project_root)
            return handle_upload(
                effective_request, matched_upload, request.body or b"", storage, SystemClock(),
                logger=logger, upload_log_path=project_root / config.logs.uploads,
            )

    if fastcgi_client is not None and (
        matched_fastcgi := resolve_zone(match_path, list(tables.fastcgi_zones))
    ) is not None:
        fastcgi_config = matched_fastcgi.data
        if not fastcgi_config.enabled:
            # Zone arretee pour maintenance (§8.1) : ni ses scripts, ni un fichier du webroot au meme chemin.
            return HttpResponse.empty(HttpStatus.SERVICE_UNAVAILABLE)
        fastcgi_resolver = SafePathResolver(filesystem, project_root / fastcgi_config.script_root)
        from omega_serv.application.server.serve_fastcgi import serve_fastcgi
        return await serve_fastcgi(
            effective_request, fastcgi_config, fastcgi_resolver, filesystem, fastcgi_client, project_root,
            config.server.server_name or config.server.bind, config.server.port,
        )

    if (
        tables.proxy_zones is not None and proxy_client is not None and proxy_load_balancer is not None
        and proxy_health_state is not None
    ):
        matched_proxy_zone = resolve_proxy_zone(match_path, list(tables.proxy_zones))
        if matched_proxy_zone is not None:
            from omega_serv.application.server.serve_proxy import ForwardingContext, serve_proxy
            return await serve_proxy(
                effective_request, matched_proxy_zone, proxy_client, proxy_load_balancer, proxy_health_state,
                proxy_client_ssl_context_verified, proxy_client_ssl_context_unverified,
                proxy_cache_store, proxy_cache_locks, proxy_cache_metrics,
                max_body_bytes=tables.proxy_max_response_body_bytes,
                log_error=_error_logger(logger, project_root, config, request.request_id),
                forwarding=ForwardingContext(config.server.port, tables.trusted_networks),
            )

    return serve_static_file(
        effective_request, path_resolver, filesystem, config.security, config.server.index_files,
        dirlisting_zones=dirlisting_zones, dirlisting_settings=dirlisting_settings,
        cache_policy=cache_policy,
        access_control_override=_access_control_override(tables, match_path),
    )
