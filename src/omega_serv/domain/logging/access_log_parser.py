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

from omega_serv.domain.logging.access_log_format import MONTH_ABBREVIATIONS

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
    path: str = ""
    """Champ additif (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md, lot 4.5 :
    "Verifier contre mes logs") - chemin de la ligne de requete, query
    comprise, tel qu'ecrit dans le log. Vide si la ligne de requete est
    illisible. Defaut "" : meme raison que `response_size`."""


def parse_apache_timestamp(text: str) -> datetime:
    """Lot 1 (D41) : `12/Nov/2026:10:00:00 +0000`, mois anglais lu sans dependre de la locale (`%b` de strptime la
    suit aussi). ValueError si la date est illisible."""
    day, month, rest = text.split("/", 2)
    if month not in MONTH_ABBREVIATIONS:
        raise ValueError(f"mois inconnu : {month!r}")
    return datetime.strptime(f"{day}/{MONTH_ABBREVIATIONS.index(month) + 1:02d}/{rest}", "%d/%m/%Y:%H:%M:%S %z")


def parse_combined_log_line(line: str) -> ParsedAccessLogEntry | None:
    match = _LINE_RE.match(line.strip())
    if match is None:
        return None
    try:
        timestamp = parse_apache_timestamp(match.group("timestamp"))
    except ValueError:
        return None
    raw_size = match.group("size")
    response_size = int(raw_size) if raw_size.isdigit() else 0
    return ParsedAccessLogEntry(
        ip=match.group("ip"),
        timestamp=timestamp,
        status_code=int(match.group("status")),
        response_size=response_size,
        path=_request_path(match.group("request")),
    )


def _request_path(request_line: str) -> str:
    parts = request_line.split(" ")
    return parts[1] if len(parts) >= 2 else ""
