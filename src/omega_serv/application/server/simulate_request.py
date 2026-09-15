# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : `omega-serv simulate-request` (spec §25.2).

Reutilise directement route_request() (meme decision que produirait
une vraie requete reseau) plutot que de dupliquer la logique de
routage - ajoute seulement les champs de diagnostic que la spec demande
(chemin normalise, raison de refus). Alias/rewrite, zone, decision WAF
et auth requise seront ajoutes a ce meme rapport au fur et a mesure que
ces phases introduisent les mecanismes correspondants (Phase 4/5/7),
jamais anticipes a vide ici."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.application.server.route_request import route_request
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.access_policy import is_denied_path, is_method_allowed
from omega_serv.domain.security.security_headers import apply_security_headers
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.ports.fastcgi_client_port import FastCgiClientPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class SimulationReport:
    method: str
    raw_path: str
    normalized_path: str | None
    method_allowed: bool
    denied_by_access_policy: bool
    file_exists: bool | None
    response_status: int
    response_headers: dict[str, str]
    rejection_reason: str | None


async def simulate_request(
    method: str,
    path: str,
    config: OmegaServConfig,
    path_resolver: SafePathResolver,
    filesystem: FilesystemPort,
    project_root: Path,
    fastcgi_client: FastCgiClientPort | None = None,
) -> SimulationReport:
    request = HttpRequest(
        request_id="simulate",
        remote_ip="127.0.0.1",
        peer_ip="127.0.0.1",
        method=method,
        path=path,
        raw_path=path,
        query="",
        headers=HttpHeaders.from_pairs([]),
        body=None,
        content_length=None,
        is_tls=False,
    )

    resolved = path_resolver.resolve(path)
    normalized_path = "/" + "/".join(resolved.segments) if resolved.ok else None
    denied = is_denied_path(resolved.segments, config.security) if resolved.ok else False
    file_exists = filesystem.is_file(resolved.absolute_path) if (resolved.ok and resolved.absolute_path) else None
    rejection_reason = resolved.rejection_reason.name if not resolved.ok and resolved.rejection_reason else None

    response = await route_request(request, path_resolver, filesystem, config, project_root, fastcgi_client)
    apply_security_headers(response, config.security, config.tls.enabled)

    return SimulationReport(
        method=method,
        raw_path=path,
        normalized_path=normalized_path,
        method_allowed=is_method_allowed(method, config.security),
        denied_by_access_policy=denied,
        file_exists=file_exists,
        response_status=int(response.status),
        response_headers=dict(response.headers),
        rejection_reason=rejection_reason,
    )
