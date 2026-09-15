# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Formatage pur des lignes de log (spec §23.2/§23.4).

Format "combined" (Apache, compatible avec les outils d'analyse
existants comme lnav/goaccess) etendu d'un champ request_id final -
extension non destructive, ignorable par tout outil qui ne le connait
pas. Aucune I/O ici : l'ecriture reelle est deleguee a
infrastructure/logging/file_line_logger.py via LoggerPort.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

_CONTROL_CHARS = frozenset(chr(c) for c in range(0x20))


def sanitize_log_field(value: str, max_length: int = 512) -> str:
    """Protection contre l'injection de log (spec §23.4) : les champs
    venant du client (referer, user-agent, chemin) doivent avoir leurs
    caracteres de controle (dont CR/LF) neutralises et leur longueur
    bornee avant ecriture."""
    cleaned = "".join(" " if ch in _CONTROL_CHARS else ch for ch in value)
    return cleaned[:max_length]


def _format_apache_timestamp(ts: datetime) -> str:
    offset = ts.strftime("%z") or "+0000"
    return f"{ts.strftime('%d/%b/%Y:%H:%M:%S')} {offset}"


@dataclass(frozen=True)
class AccessLogEntry:
    remote_ip: str
    timestamp: datetime
    method: str
    request_target: str
    http_version: str
    status_code: int
    response_size: int
    referer: str | None
    user_agent: str | None
    request_id: str


def format_combined_log_line(entry: AccessLogEntry) -> str:
    request_line = f"{entry.method} {entry.request_target} {entry.http_version}"
    referer = entry.referer or "-"
    user_agent = entry.user_agent or "-"
    size = str(entry.response_size) if entry.response_size else "-"
    return (
        f'{sanitize_log_field(entry.remote_ip, 64)} - - '
        f'[{_format_apache_timestamp(entry.timestamp)}] '
        f'"{sanitize_log_field(request_line, 2048)}" '
        f'{entry.status_code} {size} '
        f'"{sanitize_log_field(referer, 512)}" "{sanitize_log_field(user_agent, 256)}" '
        f'{sanitize_log_field(entry.request_id, 64)}'
    )


def format_error_log_line(timestamp: datetime, message: str, request_id: str | None = None) -> str:
    ts = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    suffix = f" [{sanitize_log_field(request_id, 64)}]" if request_id else ""
    return f"[{ts}] {sanitize_log_field(message, 2048)}{suffix}"
