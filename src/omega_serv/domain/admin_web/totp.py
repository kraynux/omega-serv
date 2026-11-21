"""Deuxieme facteur TOTP (RFC 6238) de l'administration web, lot 3 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md
§3.1, decisions de l'auteur du 2026-11-16).

Secret de 160 bits partage une fois avec une application du telephone (Aegis, FreeOTP, 2FAS, Google
Authenticator...) ; toutes les 30 s, chacun calcule le meme code a 6 chiffres (HMAC-SHA1 de la periode). Aucune
dependance : hmac, hashlib, base64. Code accepte pour la periode en cours ou sa voisine (+/- 30 s, derive d'horloge) ;
une periode deja acceptee pour ce compte est refusee (anti-rejeu)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import struct
from urllib.parse import quote

PERIOD_SECONDS = 30
DIGITS = 6
SECRET_BYTES = 20
WINDOW = 1
"""Periodes voisines acceptees de chaque cote."""


def new_secret(random_bytes: bytes) -> str:
    """Secret en base32 sans remplissage (forme lue par toutes les applications)."""
    if len(random_bytes) < SECRET_BYTES:
        raise ValueError("secret TOTP trop court")
    return base64.b32encode(random_bytes[:SECRET_BYTES]).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    cleaned = secret.replace(" ", "").upper()
    return base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def step_of(unix_seconds: float) -> int:
    return int(unix_seconds // PERIOD_SECONDS)


def verify(secret: str, code: str, unix_seconds: float, last_accepted_step: int | None) -> int | None:
    """Periode acceptee, ou None (code faux, mal forme, ou deja utilise). Comparaison en temps constant."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isascii() or not code.isdigit():
        return None
    try:
        _key(secret)
    except (ValueError, TypeError):
        return None
    now = step_of(unix_seconds)
    accepted = None
    for step in range(max(0, now - WINDOW), now + WINDOW + 1):  # jamais une periode avant 1970
        if hmac.compare_digest(code_at(secret, step), code) and accepted is None:
            accepted = step
    if accepted is None or (last_accepted_step is not None and accepted <= last_accepted_step):
        return None
    return accepted


def grouped(secret: str) -> str:
    """Secret par groupes de 4 (« JBSW Y3DP ... »), a taper a la main dans l'application."""
    return " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))


def otpauth_uri(secret: str, account: str, issuer: str) -> str:
    """Lien `otpauth://` : touche sur le telephone, il ouvre l'application d'authentification (methode sans scan)."""
    label = quote(f"{issuer}:{account}", safe="")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe='')}&algorithm=SHA1"
            f"&digits={DIGITS}&period={PERIOD_SECONDS}")
