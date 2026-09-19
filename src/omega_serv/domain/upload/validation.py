"""Validation metier d'un upload (pure, aucune I/O) - spec §27, plan
corrige §4. Nom de fichier restreint a une liste blanche stricte plutot
qu'une detection de '..'/'/' au cas par cas (meme principe que
domain/security/path_policy.py : une liste blanche est structurellement
plus sure qu'une liste noire)."""
from __future__ import annotations

import re

from omega_serv.domain.routing.upload_zone import UploadPolicy
from omega_serv.domain.upload.entities import UploadRequest

_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_FILENAME_LENGTH = 255


def validate_filename(filename: str) -> str | None:
    """Retourne un message d'erreur, ou None si le nom est valide."""
    if not filename or filename in (".", ".."):
        return "nom de fichier vide ou invalide"
    if len(filename) > _MAX_FILENAME_LENGTH:
        return f"nom de fichier trop long ({len(filename)} > {_MAX_FILENAME_LENGTH})"
    if not _SAFE_FILENAME_RE.match(filename):
        return "nom de fichier contient des caracteres non autorises"
    return None


def _extension_of(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_upload(request: UploadRequest, policy: UploadPolicy) -> str | None:
    """Retourne un message d'erreur, ou None si l'upload respecte la
    politique de la zone."""
    if request.size > policy.max_file_size_bytes:
        return f"fichier trop volumineux ({request.size} > {policy.max_file_size_bytes})"

    error = validate_filename(request.filename)
    if error is not None:
        return error

    extension = _extension_of(request.filename)
    if policy.allowed_extensions and extension not in policy.allowed_extensions:
        return f"extension non autorisee : {extension!r} (attendu : {list(policy.allowed_extensions)})"

    if policy.allowed_content_types and request.content_type not in policy.allowed_content_types:
        return f"Content-Type non autorise : {request.content_type!r} (attendu : {list(policy.allowed_content_types)})"

    return None
