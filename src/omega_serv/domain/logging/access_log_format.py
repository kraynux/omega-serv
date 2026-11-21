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

from omega_serv.domain.logging.error_log_line import sanitize_log_field


def _quoted_field(value: str) -> str:
    """Champ entre guillemets du journal d'acces (requete, Referer, User-Agent) : un guillemet venu du client
    devient `\\x22`, comme nginx (2026-11-02). Sinon `/a" 404 "x` fermait le champ avant l'heure : ligne illisible
    pour les statistiques, et un « 404 » fabrique par le client devant le vrai statut."""
    return value.replace('"', "\\x22")


MONTH_ABBREVIATIONS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
"""Plan proxy natif v2, lot 1 (D41) : mois du format Combined, en anglais quelle que soit la locale - `%b` suivait
LC_TIME (« nov. » en francais) et les failregex d'omega-jail, lnav et le natif ne liraient plus la ligne."""


def _format_apache_timestamp(ts: datetime) -> str:
    month = MONTH_ABBREVIATIONS[ts.month - 1]
    text = ts.strftime(f"%d/{month}/%Y:%H:%M:%S %z")
    return text + "+0000" if text.endswith(" ") else text  # date sans fuseau : UTC


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
    raw_request_line: str | None = None
    """Requete refusee pendant l'analyse de sa tete : ligne de requete brute (ou `-`), ecrite telle quelle a la
    place de « METHODE CIBLE HTTP/1.1 »."""


def format_combined_log_line(entry: AccessLogEntry) -> str:
    request_line = (
        entry.raw_request_line if entry.raw_request_line is not None
        else f"{entry.method} {entry.request_target} {entry.http_version}"
    )
    referer = entry.referer or "-"
    user_agent = entry.user_agent or "-"
    size = str(entry.response_size) if entry.response_size else "-"
    return (
        f'{sanitize_log_field(entry.remote_ip, 64)} - - '
        f'[{_format_apache_timestamp(entry.timestamp)}] '
        f'"{_quoted_field(sanitize_log_field(request_line, 2048))}" '
        f'{entry.status_code} {size} '
        f'"{_quoted_field(sanitize_log_field(referer, 512))}" "{_quoted_field(sanitize_log_field(user_agent, 256))}" '
        f'{sanitize_log_field(entry.request_id, 64)}'
    )

