# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Parsing du header `Authorization: Basic ...` (spec §15.6 : Basic
Auth encode, ne chiffre pas - ce module ne fait que decoder, jamais de
jugement sur la confidentialite du transport, qui est une
responsabilite de validation d'environnement separee)."""
from __future__ import annotations

import base64
import binascii


def parse_basic_auth_header(header_value: str | None) -> tuple[str, str] | None:
    """Retourne (username, password) ou None si l'en-tete est absent,
    malforme, ou non-Basic. Le mot de passe peut contenir ':' - seule
    la PREMIERE occurrence separe username/password (RFC 7617)."""
    if header_value is None:
        return None
    if not header_value.startswith("Basic "):
        return None

    token = header_value[len("Basic "):].strip()
    try:
        decoded_bytes = base64.b64decode(token, validate=True)
        decoded = decoded_bytes.decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None

    if ":" not in decoded:
        return None
    username, _, password = decoded.partition(":")
    return username, password


def build_www_authenticate_header(realm: str) -> str:
    return f'Basic realm="{realm}"'
