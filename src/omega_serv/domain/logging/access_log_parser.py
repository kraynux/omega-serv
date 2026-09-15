# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Parseur pur du format combine ecrit par
domain/logging/access_log_format.py::format_combined_log_line (spec
§23.2/§23.4). Jamais de logique de lecture fichier ici (delegue a
infrastructure/logging/log_parser.py) - une ligne malformee retourne
None plutot que de lever, meme discipline que domain/security/waf/
normalization.py (best-effort sur une donnee externe, jamais un rejet
bloquant pour une simple ligne de log)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_LINE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<request>[^"]*)" (?P<status>\d{3}) (?P<size>\S+) '
    r'"(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"(?: (?P<request_id>\S+))?$'
)


@dataclass(frozen=True)
class ParsedAccessLogEntry:
    ip: str
    timestamp: datetime
    status_code: int
    response_size: int = 0
    """Champ additif (retour utilisateur 2026-09-09, ecran Etat/
    Ressources) - le groupe "size" de la regex etait deja capture puis
    jete, jamais utilise jusqu'ici (compute_log_stats n'en a pas
    besoin). Defaut 0 pour ne rien casser sur les usages existants qui
    construisent cette dataclass sans le connaitre."""


def parse_combined_log_line(line: str) -> ParsedAccessLogEntry | None:
    match = _LINE_RE.match(line.strip())
    if match is None:
        return None
    try:
        timestamp = datetime.strptime(match.group("timestamp"), "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None
    raw_size = match.group("size")
    response_size = int(raw_size) if raw_size.isdigit() else 0
    return ParsedAccessLogEntry(
        ip=match.group("ip"),
        timestamp=timestamp,
        status_code=int(match.group("status")),
        response_size=response_size,
    )
