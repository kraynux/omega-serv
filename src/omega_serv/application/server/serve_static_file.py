"""Cas d'usage : servir un fichier statique, ou un listing de repertoire
optionnel (spec §16, Phase 4) quand aucun fichier index n'existe.

Orchestre le resolveur de chemin (Phase 0), les regles d'acces
generiques (domain/security/access_policy.py), le listing (domain/
routing/dirlisting.py) et le cache (domain/routing/cache_policy.py) - ne
fait jamais d'I/O directement (delegue a FilesystemPort)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.conditional import http_date, is_not_modified, make_etag, resolve_range
from omega_serv.domain.http.mime_types import guess_mime_type
from omega_serv.domain.http.precompressed import is_compressible, preferred_encodings
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.cache_policy import CachePolicy, resolve_cache_control
from omega_serv.domain.routing.dirlisting import DirlistingSettings, render_directory_listing_html
from omega_serv.domain.routing.dirlisting_sort import DirEntryInfo
from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone
from omega_serv.domain.security.access_policy import is_denied_path
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.ports.filesystem_port import FilesystemPort

_STATIC_ALLOWED_METHODS = ("GET", "HEAD")
# Au-dela, le fichier est envoye par blocs depuis le disque (HttpResponse.body_file) au lieu
# d'etre lu en memoire : memoire bornee quelle que soit sa taille, serveur jamais fige pendant
# la lecture. En dessous, une lecture directe reste la voie la plus rapide.
STREAM_THRESHOLD_BYTES = 256 * 1024


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
    display_path: str | None = None,
) -> HttpResponse:
    if request.method not in _STATIC_ALLOWED_METHODS:
        response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
        response.set_header("Allow", ", ".join(_STATIC_ALLOWED_METHODS))
        return response

    effective_display_path = display_path if display_path is not None else request.path

    resolved = path_resolver.resolve(request.path)
    if not resolved.ok:
        return HttpResponse.empty(resolved.suggested_status or HttpStatus.BAD_REQUEST)

    if not access_control_override and is_denied_path(resolved.segments, security):
        return HttpResponse.empty(HttpStatus.FORBIDDEN)

    target_path = resolved.absolute_path
    assert target_path is not None  # garanti par resolved.ok

    # Un seul stat() par chemin examine (OMEGA-SERV_ANALYSE_OPTIMISATION.md §3) : type,
    # taille et date viennent du meme appel, au lieu de is_dir + is_file + file_size +
    # file_mtime.
    info = filesystem.path_info(target_path)
    if info is not None and info.is_dir:
        for index_name in index_files:
            candidate = target_path / index_name
            candidate_info = filesystem.path_info(candidate)
            if candidate_info is not None and candidate_info.is_file:
                target_path, info = candidate, candidate_info
                break
        else:
            if resolve_zone(effective_display_path, list(dirlisting_zones)) is not None:
                return _render_listing(
                    request, target_path, filesystem, security, dirlisting_settings, effective_display_path
                )
            return HttpResponse.empty(HttpStatus.NOT_FOUND)

    if info is None or not info.is_file:
        return HttpResponse.empty(HttpStatus.NOT_FOUND)

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", guess_mime_type(target_path.name))
    if cache_policy is not None:
        response.set_header(
            "Cache-Control", resolve_cache_control(effective_display_path, target_path.name, cache_policy)
        )

    size = info.size
    mtime = info.mtime
    etag = make_etag(size, mtime)
    if is_compressible(target_path.name):
        # Etude performance, priorite 5 : version pre-compressee a cote de l'original.
        response.set_header("Vary", "Accept-Encoding")
        encoded = _precompressed_variant(request, filesystem, target_path, mtime)
        if encoded is not None:
            encoding, target_path, size, mtime = encoded
            etag = make_etag(size, mtime)[:-1] + f'-{encoding}"'
            response.set_header("Content-Encoding", encoding)
    # Validateurs (etude performance, priorite 2) : un rechargement ne coute plus qu'un 304.
    response.set_header("ETag", etag)
    response.set_header("Last-Modified", http_date(mtime))
    response.set_header("Accept-Ranges", "bytes")

    if is_not_modified(request.header("if-none-match"), request.header("if-modified-since"), etag, mtime):
        response.status = HttpStatus.NOT_MODIFIED
        return response

    if request.method == "HEAD":
        response.set_header("Content-Length", str(size))
        return response

    decision = resolve_range(request.header("range"), request.header("if-range"), size, etag, mtime)
    if decision.unsatisfiable:
        response.status = HttpStatus.RANGE_NOT_SATISFIABLE
        response.set_header("Content-Range", f"bytes */{size}")
        return response
    start, length = 0, size
    if decision.byte_range is not None:
        start, length = decision.byte_range.start, decision.byte_range.length
        response.status = HttpStatus.PARTIAL_CONTENT
        response.set_header("Content-Range", f"bytes {start}-{decision.byte_range.end}/{size}")

    if size > STREAM_THRESHOLD_BYTES:
        response.body_file = target_path
        response.body_file_offset = start
        response.body_file_length = length
    else:
        response.body = filesystem.read_bytes(target_path)[start:start + length]
    response.set_header("Content-Length", str(length))

    return response


def _precompressed_variant(
    request: HttpRequest, filesystem: FilesystemPort, original: Path, original_mtime: float,
) -> tuple[str, Path, int, float] | None:
    """(codage, fichier, taille, date) du premier `fichier.br`/`fichier.gz` accepte par le
    navigateur, dans le MEME dossier que l'original (un lien qui pointerait ailleurs est
    ignore) et au moins aussi recent que lui (jamais une version perimee)."""
    for encoding, suffix in preferred_encodings(request.header("accept-encoding")):
        candidate = original.with_name(original.name + suffix)
        info = filesystem.path_info(candidate)
        if info is None or not info.is_file:
            continue
        if filesystem.resolve_real_path(candidate).parent != original.parent:
            continue
        if info.mtime < original_mtime:
            continue
        return encoding, candidate, info.size, info.mtime
    return None


def _render_listing(
    request: HttpRequest,
    directory_path: Path,
    filesystem: FilesystemPort,
    security: SecurityConfig,
    dirlisting_settings: DirlistingSettings | None,
    display_path: str,
) -> HttpResponse:
    settings = dirlisting_settings or DirlistingSettings()
    entries = filesystem.list_directory_entries(directory_path)
    entry_info = {
        name: DirEntryInfo(
            is_directory=(is_dir := filesystem.is_dir(directory_path / name)),
            size=None if is_dir else filesystem.file_size(directory_path / name),
            mtime=filesystem.file_mtime(directory_path / name),
        )
        for name in entries
    }
    header_content = (
        _read_side_file(filesystem, directory_path, settings.header_file) if settings.show_header else None
    )
    readme_content = (
        _read_side_file(filesystem, directory_path, settings.readme_file) if settings.show_readme else None
    )
    body = render_directory_listing_html(
        display_path, entries, security, settings, header_content, readme_content, entry_info, request.query,
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
