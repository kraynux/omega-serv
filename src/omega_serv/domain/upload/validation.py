"""Validation metier d'un upload (pure, aucune I/O) - spec §27, plan
corrige §4. Nom de fichier restreint a une liste blanche stricte plutot
qu'une detection de '..'/'/' au cas par cas (meme principe que
domain/security/path_policy.py : une liste blanche est structurellement
plus sure qu'une liste noire)."""
from __future__ import annotations

import re

from omega_serv.core.i18n import _
from omega_serv.domain.routing.upload_zone import UploadPolicy
from omega_serv.domain.upload.entities import UploadRequest

_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_FILENAME_LENGTH = 255


def validate_filename(filename: str) -> str | None:
    """Retourne un message d'erreur, ou None si le nom est valide."""
    if not filename or filename in (".", ".."):
        return _("nom de fichier vide ou invalide")
    if len(filename) > _MAX_FILENAME_LENGTH:
        return _("nom de fichier trop long ({count} > {MAX_FILENAME_LENGTH})").format(count=len(filename), MAX_FILENAME_LENGTH=_MAX_FILENAME_LENGTH)
    if not _SAFE_FILENAME_RE.match(filename):
        return _("nom de fichier contient des caractères non autorisés")
    return None


def _extension_of(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_upload(request: UploadRequest, policy: UploadPolicy) -> str | None:
    """Retourne un message d'erreur, ou None si l'upload respecte la
    politique de la zone."""
    if request.size > policy.max_file_size_bytes:
        return _("fichier trop volumineux ({size} > {max_file_size_bytes})").format(size=request.size, max_file_size_bytes=policy.max_file_size_bytes)

    error = validate_filename(request.filename)
    if error is not None:
        return error

    extension = _extension_of(request.filename)
    if policy.allowed_extensions and extension not in policy.allowed_extensions:
        return _("extension non autorisée : {extension!r} (attendu : {value})").format(extension=extension, value=list(policy.allowed_extensions))

    if policy.allowed_content_types and request.content_type not in policy.allowed_content_types:
        return _("Content-Type non autorisé : {content_type!r} (attendu : {value})").format(content_type=request.content_type, value=list(policy.allowed_content_types))

    return None
