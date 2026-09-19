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

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.application.server.healthz import HEALTHZ_PATH, handle_healthz
from omega_serv.application.server.serve_fastcgi import serve_fastcgi
from omega_serv.application.server.serve_icon import ICON_URL_PREFIX, handle_icon_request
from omega_serv.application.server.serve_proxy import serve_proxy
from omega_serv.application.server.serve_static_file import serve_static_file
from omega_serv.application.upload.handle_upload import handle_upload
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.access_rule import has_explicit_allow_match, parse_access_rules
from omega_serv.domain.routing.alias import parse_alias_rules
from omega_serv.domain.routing.cache_policy import CachePolicy, parse_cache_policy
from omega_serv.domain.routing.dirlisting import DirlistingSettings
from omega_serv.domain.routing.fastcgi_zone import parse_fastcgi_config
from omega_serv.domain.routing.proxy_zone import (
    ProxyRoundRobinState,
    parse_proxy_zones,
    resolve_proxy_zone,
)
from omega_serv.domain.routing.redirect import parse_redirect_rules
from omega_serv.domain.routing.rewrite import apply_rewrites, parse_rewrite_rules
from omega_serv.domain.routing.upload_zone import UploadZoneRule, parse_upload_zone_rules
from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.infrastructure.upload.filesystem_upload_storage import FilesystemUploadStorage
from omega_serv.ports.fastcgi_client_port import FastCgiClientPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort
from omega_serv.ports.logger_port import LoggerPort


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


def _access_control_override(config: OmegaServConfig, path: str) -> bool:
    settings = _option_settings(config, "access_control")
    if settings is None:
        return False
    return has_explicit_allow_match(path, parse_access_rules(settings.get("list", [])))


async def route_request(
    request: HttpRequest,
    path_resolver: SafePathResolver,
    filesystem: FilesystemPort,
    config: OmegaServConfig,
    project_root: Path,
    fastcgi_client: FastCgiClientPort | None = None,
    logger: LoggerPort | None = None,
    proxy_client: HttpProxyClientPort | None = None,
    proxy_round_robin: ProxyRoundRobinState | None = None,
    proxy_client_ssl_context_verified: ssl.SSLContext | None = None,
    proxy_client_ssl_context_unverified: ssl.SSLContext | None = None,
) -> HttpResponse:
    if request.path == HEALTHZ_PATH:
        return handle_healthz(request)

    if request.path.startswith(ICON_URL_PREFIX):
        return handle_icon_request(request)

    redirect_settings = _option_settings(config, "redirects")
    if redirect_settings is not None:
        redirect_rules = parse_redirect_rules(redirect_settings.get("list", []))
        redirect_zones = [Zone(rule.url_prefix, rule) for rule in redirect_rules]
        matched_redirect = resolve_zone(request.path, redirect_zones)
        if matched_redirect is not None:
            response = HttpResponse.empty(HttpStatus(matched_redirect.data.status_code))
            response.set_header("Location", matched_redirect.data.destination)
            return response

    effective_path = request.path
    rewrite_settings = _option_settings(config, "rewrites")
    if rewrite_settings is not None:
        rewrite_rules = parse_rewrite_rules(rewrite_settings.get("list", []))
        result = apply_rewrites(effective_path, rewrite_rules)
        if result.loop_detected:
            return HttpResponse.empty(HttpStatus.INTERNAL_SERVER_ERROR)
        effective_path = result.final_path

    effective_request = request if effective_path == request.path else replace(request, path=effective_path)

    dirlisting_zones = _dirlisting_zones(config)
    dirlisting_settings = _dirlisting_settings(config)
    cache_policy = _cache_policy(config)

    alias_settings = _option_settings(config, "aliases")
    if alias_settings is not None:
        alias_rules = parse_alias_rules(alias_settings.get("list", []))
        alias_zones = [Zone(rule.url_prefix, rule) for rule in alias_rules]
        matched_alias = resolve_zone(effective_path, alias_zones)
        if matched_alias is not None:
            alias_rule = matched_alias.data
            remaining = effective_path[len(alias_rule.url_prefix):].lstrip("/")
            alias_request = replace(effective_request, path="/" + remaining)
            alias_resolver = SafePathResolver(filesystem, project_root / alias_rule.target_path)
            return serve_static_file(
                alias_request, alias_resolver, filesystem, config.security, config.server.index_files,
                dirlisting_zones=dirlisting_zones, dirlisting_settings=dirlisting_settings,
                cache_policy=cache_policy,
                access_control_override=_access_control_override(config, effective_path),
            )

    if request.method == "POST":
        upload_zones = _upload_zones(config)
        matched_upload = resolve_zone(effective_path, list(upload_zones))
        if matched_upload is not None:
            storage = FilesystemUploadStorage(filesystem, project_root)
            return handle_upload(
                effective_request, matched_upload, request.body or b"", storage, SystemClock(),
                logger=logger, upload_log_path=project_root / config.logs.uploads,
            )

    fastcgi_settings = _option_settings(config, "fastcgi")
    if fastcgi_settings is not None and fastcgi_client is not None:
        fastcgi_config = parse_fastcgi_config(fastcgi_settings)
        if effective_path.startswith(fastcgi_config.url_prefix):
            fastcgi_resolver = SafePathResolver(filesystem, project_root / fastcgi_config.script_root)
            return await serve_fastcgi(
                effective_request, fastcgi_config, fastcgi_resolver, filesystem, fastcgi_client, project_root,
                config.server.server_name or config.server.bind, config.server.port,
            )

    proxy_settings = _option_settings(config, "reverse_proxy")
    if proxy_settings is not None and proxy_client is not None and proxy_round_robin is not None:
        proxy_zones = parse_proxy_zones(proxy_settings.get("zones", []))
        matched_proxy_zone = resolve_proxy_zone(effective_path, proxy_zones)
        if matched_proxy_zone is not None:
            return await serve_proxy(
                effective_request, matched_proxy_zone, proxy_client, proxy_round_robin,
                proxy_client_ssl_context_verified, proxy_client_ssl_context_unverified,
            )

    return serve_static_file(
        effective_request, path_resolver, filesystem, config.security, config.server.index_files,
        dirlisting_zones=dirlisting_zones, dirlisting_settings=dirlisting_settings,
        cache_policy=cache_policy,
        access_control_override=_access_control_override(config, effective_path),
    )
