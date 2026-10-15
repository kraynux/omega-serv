"""Parseur generique multi-format pour `domain/logs/models.py::LogEntry`
(gestion des logs, refonte menu 2026-10-15) - porte verbatim depuis
omega-log (lui-meme porte depuis omega-fire, deja corrige en
performance la-bas : un seul motif precompile par categorie plutot que
plusieurs regex recompiles par ligne, mesure environ 10x plus rapide
sur un access log de ~35000 lignes).

Detection PAR HEURISTIQUE de mots-cles (AUTH/FAIL2BAN/ACCESS/KERN/
SYSLOG) - aucun parseur dedie pour auditd/pacman/samba/json-file, a
etendre au fil des besoins reels plutot qu'anticipe a vide. Distinct de
`domain/logging/access_log_parser.py` (strictement le format Combined/
Common, deja utilise par les ecrans existants) : ce module sert a
afficher/analyser N'IMPORTE QUEL log ajoute a la Bibliotheque, pas
seulement ceux propres a Omega-Serv."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from omega_serv.domain.logs.models import LogEntry, LogLevel, LogSource

IPV4_PATTERN = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
IPV6_PATTERN = r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
IP_PATTERN = rf"(?:{IPV4_PATTERN}|{IPV6_PATTERN})"
_IP_RE = re.compile(IP_PATTERN)

SYSLOG_TIMESTAMP = r"(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})"
ISO_TIMESTAMP = r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})"
APACHE_TIMESTAMP = r"\[(\d{2})/(\w{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})"

_SYSLOG_TIMESTAMP_RE = re.compile(SYSLOG_TIMESTAMP)
_ISO_TIMESTAMP_RE = re.compile(ISO_TIMESTAMP)
_APACHE_TIMESTAMP_RE = re.compile(APACHE_TIMESTAMP)

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

COMBINED_LOG_PATTERN = re.compile(
    r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)[^"]*"\s+(?P<status>\d+)\s+(?P<size>\d+|-)'
)
"""Format Combined/Common (IP - - [date] "METHODE CHEMIN HTTP/x.x" STATUT
TAILLE) - sert UNIQUEMENT a extraire les champs HTTP d'une ligne qui y
ressemble, parmi N'IMPORTE QUEL format de log parcouru ici ; ne remplace
jamais `domain/logging/access_log_parser.py`, qui reste le parseur
canonique pour le propre access log d'Omega-Serv."""

LOG_LEVELS = {
    "debug": LogLevel.DEBUG,
    "info": LogLevel.INFO,
    "information": LogLevel.INFO,
    "notice": LogLevel.INFO,
    "warning": LogLevel.WARNING,
    "warn": LogLevel.WARNING,
    "error": LogLevel.ERROR,
    "err": LogLevel.ERROR,
    "critical": LogLevel.CRITICAL,
    "crit": LogLevel.CRITICAL,
    "fatal": LogLevel.CRITICAL,
    "alert": LogLevel.CRITICAL,
    "emergency": LogLevel.CRITICAL,
    "emerg": LogLevel.CRITICAL,
}

_LOG_LEVEL_RE = re.compile(r"\b(" + "|".join(LOG_LEVELS) + r")\b")
"""Un seul motif (alternance) pour reperer tous les mots de niveau en
une seule passe par ligne - `extract_log_level()` reparcourt ensuite
`LOG_LEVELS` dans son ordre d'origine (premiere cle presente dans
l'ensemble trouve) pour preserver la priorite (le niveau le plus
specifique l'emporte), jamais le premier mot rencontre dans le texte."""

_SERVICE_RE = re.compile(r"\w+\s+([a-zA-Z0-9_-]+)(?:\[\d+\])?:")

_USER_PATTERNS = [
    re.compile(r"user\s+([a-zA-Z0-9_-]+)", re.IGNORECASE),
    re.compile(r"for\s+([a-zA-Z0-9_-]+)", re.IGNORECASE),
    re.compile(r"Accepted\s+\w+\s+for\s+([a-zA-Z0-9_-]+)", re.IGNORECASE),
    re.compile(r"Failed\s+\w+\s+for\s+([a-zA-Z0-9_-]+)", re.IGNORECASE),
]

_PORT_PATTERNS = [
    re.compile(r"port\s+(\d+)"),
    re.compile(r":(\d+)\b"),
]


def extract_ip(line: str) -> str | None:
    match = _IP_RE.search(line)
    return match.group(0) if match else None


def extract_all_ips(line: str) -> list[str]:
    return _IP_RE.findall(line)


def extract_timestamp(line: str) -> datetime | None:
    """Formats geres : syslog (Jan 1 12:00:00), ISO (2026-01-01T12:00:00),
    Apache/Nginx Combined ([10/Oct/2026:10:00:00 +0200]). Toujours
    renvoye en UTC (`tzinfo=timezone.utc`) - meme convention que
    `ports/clock_port.py`/`SystemClock` (jamais une datetime naive dans
    ce projet, comparaisons avec `datetime.now(timezone.utc)` sinon
    impossibles). Les formats sans fuseau explicite (syslog/ISO sans
    offset) sont donc traites comme deja exprimes en UTC - une
    approximation assumee (l'heure affichee a l'ecran peut differer de
    l'heure locale reelle de la machine qui a ecrit la ligne), jamais
    une erreur de comparaison relative entre lignes d'un meme fichier."""
    iso_match = _ISO_TIMESTAMP_RE.search(line)
    if iso_match:
        try:
            year, month, day, hour, minute, second = (int(g) for g in iso_match.groups())
            return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        except ValueError:
            pass

    apache_match = _APACHE_TIMESTAMP_RE.search(line)
    if apache_match:
        day_s, month_s, year_s, hour_s, minute_s, second_s = apache_match.groups()
        apache_month = _MONTH_ABBR.get(month_s.lower())
        if apache_month is not None:
            try:
                return datetime(
                    int(year_s), apache_month, int(day_s), int(hour_s), int(minute_s), int(second_s),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                pass

    syslog_match = _SYSLOG_TIMESTAMP_RE.search(line)
    if syslog_match:
        month_s, day_s, hour_s, minute_s, second_s = syslog_match.groups()
        syslog_month = _MONTH_ABBR.get(month_s.lower())
        if syslog_month is not None:
            try:
                return datetime(
                    datetime.now(timezone.utc).year, syslog_month, int(day_s), int(hour_s), int(minute_s),
                    int(second_s), tzinfo=timezone.utc,
                )
            except ValueError:
                pass

    return None


def extract_log_level(line: str) -> LogLevel:
    line_lower = line.lower()
    found = set(_LOG_LEVEL_RE.findall(line_lower))
    if not found:
        return LogLevel.INFO
    for level_str, level_enum in LOG_LEVELS.items():
        if level_str in found:
            return level_enum
    return LogLevel.INFO


def extract_service(line: str) -> str | None:
    match = _SERVICE_RE.search(line)
    return match.group(1) if match else None


def extract_user(line: str) -> str | None:
    for pattern in _USER_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group(1)
    return None


def extract_port(line: str) -> int | None:
    for pattern in _PORT_PATTERNS:
        match = pattern.search(line)
        if match:
            try:
                port = int(match.group(1))
                if 1 <= port <= 65535:
                    return port
            except ValueError:
                pass
    return None


def extract_http_fields(line: str) -> tuple[str | None, str | None, int | None, int | None]:
    """(methode, chemin, code HTTP, latence_ms) - None partout si la
    ligne ne ressemble pas a du Combined/Common (jamais le cas pour
    auth/syslog/fail2ban, ces champs n'ont alors pas de sens). Latence :
    heuristique (dernier jeton numerique court <= 6 chiffres apres la
    partie matchee - convention pour un format qui ajoute la duree en
    fin de ligne, ex. directive Apache "%D"/"%T"), absente du Common Log
    Format standard - jamais une valeur inventee."""
    match = COMBINED_LOG_PATTERN.search(line)
    if not match:
        return None, None, None, None

    status = int(match.group("status"))
    tail = line[match.end():].strip().split()
    latency_ms: int | None = None
    for token in reversed(tail):
        clean_token = token.strip('"').replace(".", "")
        if clean_token.isdigit() and len(clean_token) <= 6:
            latency_ms = int(clean_token)
            break

    return match.group("method"), match.group("path"), status, latency_ms


def detect_log_source(line: str) -> LogSource:
    line_lower = line.lower()

    if any(indicator in line_lower for indicator in [
        "sshd", "sudo", "authentication", "login", "accepted password",
        "failed password", "invalid user",
    ]):
        return LogSource.AUTH

    if "fail2ban" in line_lower:
        return LogSource.FAIL2BAN

    if any(indicator in line_lower for indicator in [
        "get /", "post /", "http/", "404", "500", "apache", "nginx",
    ]):
        return LogSource.ACCESS

    if any(indicator in line_lower for indicator in [
        "kernel:", "iptables", "nftables", "netfilter",
    ]):
        return LogSource.KERN

    return LogSource.SYSLOG


def parse_log_line(
    line: str, line_number: int = 0, log_path: str | None = None, source: LogSource | None = None,
) -> LogEntry | None:
    if not line.strip():
        return None

    timestamp = extract_timestamp(line)
    ip = extract_ip(line)
    level = extract_log_level(line)
    service = extract_service(line)
    user = extract_user(line)
    port = extract_port(line)
    http_method, http_path, http_status, latency_ms = extract_http_fields(line)

    if source is None:
        source = detect_log_source(line)

    if http_status is not None and http_status >= 400 and level == LogLevel.INFO:
        # Un 4xx/5xx est un echec meme sans mot-cle de niveau explicite (le cas
        # courant pour un access log Combined standard) - jamais ecrase si un
        # niveau plus specifique a deja ete detecte par ailleurs.
        level = LogLevel.ERROR if http_status >= 500 else LogLevel.WARNING

    return LogEntry(
        timestamp=timestamp or datetime.now(timezone.utc),
        source=source,
        level=level,
        ip=ip,
        message=line.strip(),
        raw_line=line,
        line_number=line_number,
        log_path=log_path,
        user=user,
        port=port,
        http_method=http_method,
        http_path=http_path,
        http_status=http_status,
        latency_ms=latency_ms,
        service=service,
    )


def parse_log_lines(
    lines: list[str], log_path: str | None = None, source: LogSource | None = None,
) -> list[LogEntry]:
    entries = []
    for i, line in enumerate(lines, start=1):
        entry = parse_log_line(line, line_number=i, log_path=log_path, source=source)
        if entry is not None:
            entries.append(entry)
    return entries
