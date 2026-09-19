"""Modeles purs des statistiques de logs (plan interface §3.4/§8) -
memes formes de donnees generiques que omega-fire (core/stats/models.py::
IpStat/LogStatsSummary), contenu adapte : SERV n'a ni jails ni bans
(fail2ban), seulement des requetes HTTP - top IPs par nombre de
requetes, repartition par code de statut, repartition horaire."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class IpStat:
    ip: str
    count: int
    last_seen: datetime


@dataclass(frozen=True)
class LogStatsSummary:
    period_label: str
    start: datetime
    end: datetime
    total_requests: int = 0
    top_ips: tuple[IpStat, ...] = field(default_factory=tuple)
    status_code_counts: dict[int, int] = field(default_factory=dict)
    hourly_counts: tuple[int, ...] = field(default_factory=lambda: (0,) * 24)
