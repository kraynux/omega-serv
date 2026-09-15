# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : servir une requete via FastCGI/PHP-FPM (spec §21).

Reutilise SafePathResolver.resolve() confine a script_root (meme
garantie de confinement que les alias, Phase 4 - "le handler statique
ne peut structurellement jamais divulguer le code source PHP" vaut
aussi ici : un chemin qui sort de script_root est rejete exactement
comme un chemin qui sortirait de webroot). N'applique jamais les
en-tetes de securite serveur lui-meme (HttpResponse.set_header, jamais
force_security_header) - le pipeline appelant les impose apres, de
maniere non negociable, meme sur une reponse FastCGI (decision deja
actee au niveau de domain/http/response.py)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.http.cgi_env import build_cgi_env
from omega_serv.domain.http.fastcgi_protocol import FastCgiConnectionError
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.fastcgi_zone import FastCgiConfig
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.ports.fastcgi_client_port import FastCgiClientPort
from omega_serv.ports.filesystem_port import FilesystemPort


async def serve_fastcgi(
    request: HttpRequest,
    fastcgi_config: FastCgiConfig,
    resolver: SafePathResolver,
    filesystem: FilesystemPort,
    fastcgi_client: FastCgiClientPort,
    project_root: Path,
    server_name: str,
    server_port: int,
) -> HttpResponse:
    remaining = request.path[len(fastcgi_config.url_prefix):].lstrip("/")
    resolved = resolver.resolve("/" + remaining)
    if not resolved.ok:
        return HttpResponse.empty(resolved.suggested_status or HttpStatus.BAD_REQUEST)

    target = resolved.absolute_path
    assert target is not None  # garanti par resolved.ok

    if filesystem.is_dir(target):
        for index_name in fastcgi_config.index_files:
            candidate = target / index_name
            if filesystem.is_file(candidate):
                target = candidate
                break
        else:
            return HttpResponse.empty(HttpStatus.NOT_FOUND)

    if not filesystem.is_file(target):
        return HttpResponse.empty(HttpStatus.NOT_FOUND)

    if fastcgi_config.allowed_scripts:
        # Liste blanche explicite (retour utilisateur 2026-09-09) :
        # seuls ces scripts precis sont executables, meme si d'autres
        # fichiers .php existent sous script_root (helpers/inclusions
        # jamais destines a etre appeles directement en URL).
        relative = target.relative_to(resolver.webroot).as_posix()
        if relative not in fastcgi_config.allowed_scripts:
            return HttpResponse.empty(HttpStatus.FORBIDDEN)
    elif not any(target.name.endswith(ext) for ext in fastcgi_config.allowed_extensions):
        # Comportement historique (retro-compatible) si aucune liste
        # blanche n'est configuree : un fichier existe mais n'est pas
        # un script PHP (ex. .txt oublie sous script_root) - 403,
        # jamais servi tel quel : ce handler ne doit jamais devenir un
        # serveur statique alternatif.
        return HttpResponse.empty(HttpStatus.FORBIDDEN)

    env = build_cgi_env(
        request,
        script_filename=str(target),
        script_name=request.path,
        document_root=str(resolver.webroot),
        server_name=server_name,
        server_port=server_port,
    )

    socket_path = project_root / fastcgi_config.socket_path
    try:
        result = await fastcgi_client.send_request(
            socket_path, env, request.body or b"",
            fastcgi_config.connect_timeout_seconds, fastcgi_config.read_timeout_seconds,
        )
    except FastCgiConnectionError:
        return HttpResponse.empty(HttpStatus.SERVICE_UNAVAILABLE)

    response = HttpResponse.empty(result.status_code)
    for name, value in result.headers:
        response.set_header(name, value)
    response.body = result.body
    return response
