"""Libelles du rapport de Statistiques partages par l'ecran et l'export (2026-11-07, porte d'omega-log) :
traduits a l'appel, donc dans la langue de l'interface a l'ecran et dans celle des exports dans le
processus enfant d'export (voir `DependencyContainer.export_payload`)."""
from __future__ import annotations

from omega_serv.core.i18n import N_, _

PERIOD_LABELS: dict[str | None, str] = {
    "24h": N_("24 dernières heures"), "7d": N_("7 derniers jours"), "30d": N_("30 derniers jours"),
    None: N_("tout le fichier"),
}


def period_label(period: str | None) -> str:
    return _(PERIOD_LABELS.get(period, PERIOD_LABELS[None]))


def format_bytes(size: float) -> str:
    for unit, factor in ((_("Go"), 1024 ** 3), (_("Mo"), 1024 ** 2), (_("Ko"), 1024)):
        if size >= factor:
            return f"{size / factor:.1f} {unit}"
    return f"{int(size)} o"


def stats_export_payload(sources: list[str], period: str | None, report: dict) -> dict:
    """Donnees du rapport HTML ; `report` = `dataclasses.asdict(StatsReport)`."""
    return {"sources": sources, "period": period, "report": report}


def stats_html_arguments(payload: dict) -> dict:
    """Arguments de `export_log_stats_html` traduits ICI (periode, volume)."""
    report = payload["report"]
    bytes_total = report.get("bytes_total")
    return {
        "sources": payload["sources"],
        "period_label": period_label(payload["period"]),
        "report": report,
        "volume": "-" if bytes_total is None else format_bytes(bytes_total),
    }
