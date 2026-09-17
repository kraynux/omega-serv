# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : servir un fichier statique, ou un listing de repertoire
optionnel (spec §16, Phase 4) quand aucun fichier index n'existe.

Orchestre le resolveur de chemin (Phase 0), les regles d'acces
generiques (domain/security/access_policy.py), le listing (domain/
routing/dirlisting.py) et le cache (domain/routing/cache_policy.py) - ne
fait jamais d'I/O directement (delegue a FilesystemPort)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.mime_types import guess_mime_type
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.cache_policy import CachePolicy, resolve_cache_control
from omega_serv.domain.routing.dirlisting import DirlistingSettings, render_directory_listing_html
from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone
from omega_serv.domain.security.access_policy import is_denied_path
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.ports.filesystem_port import FilesystemPort

_STATIC_ALLOWED_METHODS = ("GET", "HEAD")


def serve_static_file(
    request: HttpRequest,
    path_resolver: SafePathResolver,
    filesystem: FilesystemPort,
    security: SecurityConfig,
    index_files: tuple[str, ...],
    dirlisting_zones: tuple[Zone[bool], ...] = (),
    dirlisting_settings: DirlistingSettings | None = None,
    cache_policy: CachePolicy | None = None,
    access_control_override: bool = False,
) -> HttpResponse:
    if request.method not in _STATIC_ALLOWED_METHODS:
        response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
        response.set_header("Allow", ", ".join(_STATIC_ALLOWED_METHODS))
        return response

    resolved = path_resolver.resolve(request.path)
    if not resolved.ok:
        return HttpResponse.empty(resolved.suggested_status or HttpStatus.BAD_REQUEST)

    if not access_control_override and is_denied_path(resolved.segments, security):
        # access_control_override (domain/routing/access_rule.py) : une
        # regle "allow" explicite sur ce chemin exact (retour
        # utilisateur 2026-09-09, ex: re-autoriser /private/.assets/
        # sous un /private/ par ailleurs bloque) leve deliberement les
        # regles globales dotfile/motif/extension - l'administrateur a
        # explicitement declare ce chemin public, ce qui prime sur une
        # heuristique generique.
        return HttpResponse.empty(HttpStatus.FORBIDDEN)

    target_path = resolved.absolute_path
    assert target_path is not None  # garanti par resolved.ok

    if filesystem.is_dir(target_path):
        for index_name in index_files:
            candidate = target_path / index_name
            if filesystem.is_file(candidate):
                target_path = candidate
                break
        else:
            if resolve_zone(request.path, list(dirlisting_zones)) is not None:
                return _render_listing(request, target_path, filesystem, security, dirlisting_settings)
            return HttpResponse.empty(HttpStatus.NOT_FOUND)

    if not filesystem.is_file(target_path):
        return HttpResponse.empty(HttpStatus.NOT_FOUND)

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", guess_mime_type(target_path.name))
    if cache_policy is not None:
        response.set_header("Cache-Control", resolve_cache_control(request.path, target_path.name, cache_policy))

    if request.method == "HEAD":
        response.set_header("Content-Length", str(filesystem.file_size(target_path)))
    else:
        body = filesystem.read_bytes(target_path)
        response.body = body
        response.set_header("Content-Length", str(len(body)))

    return response


def _render_listing(
    request: HttpRequest,
    directory_path: Path,
    filesystem: FilesystemPort,
    security: SecurityConfig,
    dirlisting_settings: DirlistingSettings | None,
) -> HttpResponse:
    settings = dirlisting_settings or DirlistingSettings()
    entries = filesystem.list_directory_entries(directory_path)
    # Retour utilisateur ("on ne fait pas la difference entre un fichier
    # et un dossier") : render_directory_listing_html() reste pur (aucun
    # FilesystemPort) - la distinction fichier/dossier est donc calculee
    # ICI, seul endroit avec un acces I/O reel, puis transmise en pur
    # ensemble de noms.
    directory_names = frozenset(name for name in entries if filesystem.is_dir(directory_path / name))
    header_content = (
        _read_side_file(filesystem, directory_path, settings.header_file) if settings.show_header else None
    )
    readme_content = (
        _read_side_file(filesystem, directory_path, settings.readme_file) if settings.show_readme else None
    )
    body = render_directory_listing_html(
        request.path, entries, security, settings, header_content, readme_content, directory_names,
    ).encode("utf-8")

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "text/html; charset=utf-8")
    response.set_header("Content-Length", str(len(body)))
    if request.method == "GET":
        response.body = body
    return response


def _read_side_file(filesystem: FilesystemPort, directory_path: Path, file_name: str) -> str | None:
    """Contenu d'un fichier HEADER/README optionnel a cote du listing -
    absent la plupart du temps, jamais une erreur (spec/retour
    utilisateur : le reglage est purement optionnel, activer `show_header`/
    `show_readme` sans avoir cree le fichier ne doit rien casser)."""
    candidate = directory_path / file_name
    if not filesystem.is_file(candidate):
        return None
    return filesystem.read_text(candidate)
