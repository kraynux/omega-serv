# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Agregation reelle des statistiques d'un log d'acces (plan interface
§3.4/§8) - inspire de la structure "parse -> agrege par cle -> trie" de
omega-fire (infrastructure/logging/stats/log_aggregator.py) mais
entierement reecrit : celui de fire parse des logs pare-feu (iptables/
nftables/fail2ban via journalctl + sqlite), rien de reutilisable pour le
format Apache combined + request_id de SERV
(domain/logging/access_log_parser.py)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.logging.access_log_parser import parse_combined_log_line
from omega_serv.domain.logging.stats import IpStat, LogStatsSummary

PERIOD_SECONDS: dict[str, int] = {"24h": 24 * 3600, "7d": 7 * 24 * 3600, "30d": 30 * 24 * 3600}
_TOP_IPS_LIMIT = 20


def compute_log_stats(log_path: Path, period_label: str, now: datetime | None = None) -> LogStatsSummary:
    if now is None:
        now = datetime.now(timezone.utc)
    seconds = PERIOD_SECONDS.get(period_label, PERIOD_SECONDS["24h"])
    start = now - timedelta(seconds=seconds)

    ip_counts: Counter[str] = Counter()
    ip_last_seen: dict[str, datetime] = {}
    status_counts: Counter[int] = Counter()
    hourly = [0] * 24
    total = 0

    if log_path.exists():
        with log_path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                entry = parse_combined_log_line(line)
                if entry is None or entry.timestamp < start:
                    continue
                total += 1
                ip_counts[entry.ip] += 1
                if entry.ip not in ip_last_seen or entry.timestamp > ip_last_seen[entry.ip]:
                    ip_last_seen[entry.ip] = entry.timestamp
                status_counts[entry.status_code] += 1
                hourly[entry.timestamp.astimezone(timezone.utc).hour] += 1

    top_ips = tuple(
        IpStat(ip=ip, count=count, last_seen=ip_last_seen[ip])
        for ip, count in ip_counts.most_common(_TOP_IPS_LIMIT)
    )

    return LogStatsSummary(
        period_label=period_label,
        start=start,
        end=now,
        total_requests=total,
        top_ips=top_ips,
        status_code_counts=dict(status_counts),
        hourly_counts=tuple(hourly),
    )
