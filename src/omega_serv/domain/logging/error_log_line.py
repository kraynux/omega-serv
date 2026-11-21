"""Ligne du journal d'erreurs et neutralisation des champs (spec §23.4), sans `dataclasses` : le superviseur reduit du
moteur natif l'utilise (lot 5 memoire, 2026-11-19). `access_log_format` les reexporte pour les autres appelants."""
from __future__ import annotations

TYPE_CHECKING = False
if TYPE_CHECKING:
    from datetime import datetime

# Neutralisation des caracteres de controle 0x00-0x1F, en une passe C (str.translate) : execute plusieurs fois par requete.
_CONTROL_TO_SPACE = str.maketrans(dict.fromkeys([*range(0x20), 0x7F, *range(0x80, 0xA0), 0x2028, 0x2029], " "))
"""Scan de securite n° 2 (2026-11-20, F29) : en plus de 0x00-0x1F, DEL, les controles C1 (dont U+0085, NEL) et les
separateurs U+2028/U+2029 - des lecteurs (splitlines, visionneuses) y voient une fin de ligne. Meme liste dans le
natif (text.cpp, sanitize_log_field)."""


def sanitize_log_field(value: str, max_length: int = 512) -> str:
    """Protection contre l'injection de log (spec §23.4) : les champs
    venant du client (referer, user-agent, chemin) doivent avoir leurs
    caracteres de controle (dont CR/LF) neutralises et leur longueur
    bornee avant ecriture."""
    return value.translate(_CONTROL_TO_SPACE)[:max_length]


def format_error_log_line(timestamp: datetime, message: str, request_id: str | None = None) -> str:
    ts = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    suffix = f" [{sanitize_log_field(request_id, 64)}]" if request_id else ""
    return f"[{ts}] {sanitize_log_field(message, 2048)}{suffix}"
