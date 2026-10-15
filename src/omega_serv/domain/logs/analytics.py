"""Statistiques pures sur des `LogEntry` deja parsees (gestion des logs,
refonte menu 2026-10-15) - porte verbatim depuis omega-log (lui-meme
porte depuis omega-fire), aucune lecture fichier ici."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from omega_serv.domain.logs.models import (
    HourlyStats,
    LogEntry,
    LogLevel,
    LogSource,
    LogStats,
    TopIP,
)


def compute_top_ips(entries: list[LogEntry], n: int = 10, min_count: int = 1) -> list[TopIP]:
    ip_counts: dict[str, int] = defaultdict(int)
    ip_first_seen: dict[str, datetime] = {}
    ip_last_seen: dict[str, datetime] = {}
    ip_services: dict[str, set[str]] = defaultdict(set)
    ip_http_errors: dict[str, int] = defaultdict(int)

    for entry in entries:
        if not entry.has_ip():
            continue
        ip = entry.ip
        assert ip is not None
        ip_counts[ip] += 1
        if ip not in ip_first_seen or entry.timestamp < ip_first_seen[ip]:
            ip_first_seen[ip] = entry.timestamp
        if ip not in ip_last_seen or entry.timestamp > ip_last_seen[ip]:
            ip_last_seen[ip] = entry.timestamp
        if entry.service:
            ip_services[ip].add(entry.service)
        if entry.is_http_error():
            ip_http_errors[ip] += 1

    top_ips = []
    for ip, count in ip_counts.items():
        if count < min_count:
            continue
        top_ips.append(TopIP(
            ip=ip, count=count,
            first_seen=ip_first_seen.get(ip), last_seen=ip_last_seen.get(ip),
            services=sorted(ip_services.get(ip, [])), http_errors=ip_http_errors.get(ip, 0),
        ))

    top_ips.sort(key=lambda x: (-x.count, x.ip))
    return top_ips[:n]


def compute_hourly_stats(entries: list[LogEntry]) -> list[HourlyStats]:
    hourly: dict[int, HourlyStats] = {hour: HourlyStats(hour=hour) for hour in range(24)}
    for entry in entries:
        hour = entry.timestamp.hour
        hourly[hour].count += 1
        if entry.is_error():
            hourly[hour].error_count += 1
    return [hourly[hour] for hour in range(24)]


def compute_level_distribution(entries: list[LogEntry]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        counts[entry.level.value] += 1
    return dict(counts)


def compute_source_distribution(entries: list[LogEntry]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        counts[entry.source.value] += 1
    return dict(counts)


def compute_time_range(entries: list[LogEntry]) -> tuple[datetime | None, datetime | None]:
    if not entries:
        return None, None
    timestamps = [e.timestamp for e in entries]
    return min(timestamps), max(timestamps)


def compute_stats(entries: list[LogEntry], total_lines: int = 0, log_path: str | None = None, top_n: int = 10) -> LogStats:
    unique_ips = len({e.ip for e in entries if e.has_ip()})
    total_ips = len([e for e in entries if e.has_ip()])
    level_counts = compute_level_distribution(entries)
    source_counts = compute_source_distribution(entries)
    hourly_stats = compute_hourly_stats(entries)
    top_ips = compute_top_ips(entries, n=top_n)
    first_entry, last_entry = compute_time_range(entries)

    return LogStats(
        log_path=log_path,
        total_lines=total_lines if total_lines > 0 else len(entries),
        parsed_lines=len(entries),
        failed_lines=total_lines - len(entries) if total_lines > 0 else 0,
        unique_ips=unique_ips, total_ips=total_ips,
        level_counts=level_counts, hourly_stats=hourly_stats, top_ips=top_ips,
        first_entry=first_entry, last_entry=last_entry, source_counts=source_counts,
    )


def filter_entries_by_ip(entries: list[LogEntry], ip: str) -> list[LogEntry]:
    return [e for e in entries if e.matches_ip(ip)]


def filter_entries_by_level(entries: list[LogEntry], level: LogLevel) -> list[LogEntry]:
    return [e for e in entries if e.level == level]


def filter_entries_by_source(entries: list[LogEntry], source: LogSource) -> list[LogEntry]:
    return [e for e in entries if e.source == source]


def filter_error_entries(entries: list[LogEntry]) -> list[LogEntry]:
    return [e for e in entries if e.is_error()]
