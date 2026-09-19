"""Decodage multipart/form-data (RFC 7578), pure, aucune I/O - spec §27.

Corrige par rapport a la version initiale du plan detaille (voir
OMEGA-SERV_PLAN-DETAILLE_SOUS_SYSTEME_UPLOAD.md §0/§8.3) : le
boundary doit etre encode en bytes AVANT le split, puisque le corps
(`body`) est deja `bytes` (HttpRequest.body) alors que le boundary est
extrait comme `str` depuis l'en-tete Content-Type."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_BOUNDARY_RE = re.compile(r'boundary="?([^";]+)"?')


@dataclass(frozen=True)
class MultipartPart:
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""

    @property
    def filename(self) -> str | None:
        disposition = self.headers.get("content-disposition", "")
        match = re.search(r'filename="([^"]*)"', disposition)
        return match.group(1) if match else None

    @property
    def field_content_type(self) -> str:
        return self.headers.get("content-type", "application/octet-stream")


def extract_boundary(content_type_header: str) -> str | None:
    """Extrait le boundary declare dans l'en-tete Content-Type d'une
    requete multipart/form-data - None si absent ou si le Content-Type
    n'est pas multipart."""
    if not content_type_header.lower().startswith("multipart/"):
        return None
    match = _BOUNDARY_RE.search(content_type_header)
    return match.group(1) if match else None


def _parse_part_headers(header_blob: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_blob.split(b"\r\n"):
        if not line:
            continue
        name, _, value = line.decode("latin-1").partition(":")
        headers[name.strip().lower()] = value.strip()
    return headers


def parse_multipart(body: bytes, boundary: str) -> list[MultipartPart]:
    """Decoupe un corps multipart/form-data en parties. `boundary` est
    une chaine (telle qu'extraite de l'en-tete), encodee en bytes ici
    avant tout split sur `body` (bytes) - jamais l'inverse (bug corrige,
    voir docstring de module)."""
    boundary_bytes = b"--" + boundary.encode("ascii", errors="ignore")
    parts: list[MultipartPart] = []
    for chunk in body.split(boundary_bytes):
        piece = chunk.strip(b"\r\n")
        if not piece or piece == b"--":
            continue
        header_blob, separator, content = piece.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = _parse_part_headers(header_blob.lstrip(b"\r\n"))
        parts.append(MultipartPart(headers=headers, content=content.removesuffix(b"\r\n")))
    return parts
