"""Modeles generiques pour un log QUELCONQUE (pas uniquement l'access
log au format Combined deja couvert par domain/logging/) - gestion des
logs, refonte menu (2026-10-15). Portes verbatim depuis omega-log
(lui-meme porte depuis omega-fire), AUCUNE dependance externe - purs
modeles de domaine, jamais de lecture disque ici.

Distinct de `domain/logging/access_log_format.py` (lie au format
Combined/Common uniquement, deja utilise par les ecrans existants) :
ce module sert la Bibliotheque/Voir les logs/Voir et traiter IP, qui
doivent savoir afficher N'IMPORTE QUEL log ajoute manuellement (auth.log,
syslog, fail2ban...), pas seulement les logs propres a Omega-Serv."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LogSource(Enum):
    AUTH = "auth"
    ACCESS = "access"
    SYSLOG = "syslog"
    KERN = "kern"
    FAIL2BAN = "fail2ban"
    CUSTOM = "custom"


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """Une ligne de log parsee - pur modele de domaine, ne sait pas lire
    ou parser un fichier (voir `domain/logs/parser.py`)."""
    timestamp: datetime
    source: LogSource
    level: LogLevel = LogLevel.INFO
    ip: str | None = None
    message: str = ""
    raw_line: str = ""
    line_number: int = 0
    log_path: str | None = None

    user: str | None = None
    port: int | None = None
    protocol: str | None = None
    http_method: str | None = None
    http_path: str | None = None
    http_status: int | None = None
    latency_ms: int | None = None
    """Duree de traitement quand le format du log la fournit (ex. "%D"/
    "%T" Apache) - None si non applicable/non detectee, jamais une
    valeur inventee."""
    service: str | None = None

    def has_ip(self) -> bool:
        return self.ip is not None and self.ip != ""

    def is_error(self) -> bool:
        return self.level in (LogLevel.ERROR, LogLevel.CRITICAL)

    def is_warning_or_above(self) -> bool:
        return self.level in (LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL)

    def is_http_error(self) -> bool:
        if self.http_status is None:
            return False
        return self.http_status >= 400

    def matches_ip(self, ip: str) -> bool:
        return self.ip == ip


@dataclass
class TopIP:
    ip: str
    count: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    services: list[str] = field(default_factory=list)
    http_errors: int = 0

    def percentage(self, total: int) -> float:
        if total == 0:
            return 0.0
        return (self.count / total) * 100.0


@dataclass
class HourlyStats:
    hour: int  # 0-23
    count: int = 0
    error_count: int = 0

    def error_rate(self) -> float:
        if self.count == 0:
            return 0.0
        return (self.error_count / self.count) * 100.0


@dataclass
class LogStats:
    log_path: str | None = None
    total_lines: int = 0
    parsed_lines: int = 0
    failed_lines: int = 0

    unique_ips: int = 0
    total_ips: int = 0

    level_counts: dict[str, int] = field(default_factory=dict)
    hourly_stats: list[HourlyStats] = field(default_factory=list)
    top_ips: list[TopIP] = field(default_factory=list)

    first_entry: datetime | None = None
    last_entry: datetime | None = None

    source_counts: dict[str, int] = field(default_factory=dict)

    def parse_rate(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return (self.parsed_lines / self.total_lines) * 100.0

    def error_rate(self) -> float:
        error_count = self.level_counts.get("error", 0) + self.level_counts.get("critical", 0)
        if self.parsed_lines == 0:
            return 0.0
        return (error_count / self.parsed_lines) * 100.0

    def get_level_count(self, level: LogLevel) -> int:
        return self.level_counts.get(level.value, 0)

    def get_source_count(self, source: LogSource) -> int:
        return self.source_counts.get(source.value, 0)

    def get_hourly_stats(self, hour: int) -> HourlyStats | None:
        for stats in self.hourly_stats:
            if stats.hour == hour:
                return stats
        return None

    def time_span_hours(self) -> float:
        if self.first_entry is None or self.last_entry is None:
            return 0.0
        delta = self.last_entry - self.first_entry
        return delta.total_seconds() / 3600.0
