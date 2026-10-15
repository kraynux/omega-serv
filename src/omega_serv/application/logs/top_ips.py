"""Cas d'usage "Voir et traiter IP" (gestion des logs, refonte menu
2026-10-15, porte depuis omega-log/plan_omega_log.md §2) : top N
generalise a N'IMPORTE QUEL(S) log(s) de la Bibliotheque, plus un
support d'export CSV."""
from __future__ import annotations

from datetime import datetime

from omega_serv.application.logs.reading import read_entries_for_paths
from omega_serv.domain.logs.analytics import compute_top_ips
from omega_serv.domain.logs.models import TopIP


def compute_top_ips_for_paths(
    paths: list[str], *, period: str | None = None, n: int = 10, now: datetime | None = None,
) -> list[TopIP]:
    """Top N IP toutes sources confondues parmi `paths`. `period` filtre
    sur l'horodatage de chaque ligne ("24h"/"7d"/"30d"/None pour tout)."""
    entries = read_entries_for_paths(paths, period=period, now=now)
    return compute_top_ips(entries, n=n)
