"""Ecran Statistiques du log d'acces (plan interface §3.4/§8) - periode
24h/7d/30d, `container.compute_log_stats` (format combine uniquement,
donc access log seul - error/waf_alerts/breakage/uploads ne portent pas
d'IP/code de statut au meme format, voir domain/logging/access_log_parser.py)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_PERIODS: tuple[tuple[str, str], ...] = (
    ("24h", "24 heures"),
    ("7d", "7 jours"),
    ("30d", "30 jours"),
)
_BAR_WIDTH = 40


class LogStatsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._period = "24h"

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("STATISTIQUES DU LOG D'ACCES", classes="omega-title")
            yield Static("", id="stats-error", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                for period_id, label in _PERIODS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=f"period-{period_id}")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
            yield Static("", id="stats-summary")
            yield Static("", id="stats-hourly")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
            return
        if button_id.startswith("period-"):
            self._period = button_id.removeprefix("period-")
            self._refresh()

    def _access_log_path(self) -> Path | None:
        error_widget = self.query_one("#stats-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return None
        error_widget.update("")
        return self._container.project_root / load_result.config.logs.access

    def _refresh(self) -> None:
        log_path = self._access_log_path()
        if log_path is None:
            return

        summary = self._container.compute_log_stats(log_path, self._period)

        top_lines = "\n".join(
            f"  {ip_stat.ip:<18} {ip_stat.count:>8}  (vu la derniere fois : {ip_stat.last_seen.isoformat()})"
            for ip_stat in summary.top_ips
        ) or "  (aucune requete sur cette periode)"

        status_lines = "\n".join(
            f"  {code} : {count}" for code, count in sorted(summary.status_code_counts.items())
        ) or "  (aucun code de statut sur cette periode)"

        self.query_one("#stats-summary", Static).update(
            f"Periode : {summary.period_label} ({summary.start.isoformat()} -> {summary.end.isoformat()})\n"
            f"Total requetes : {summary.total_requests}\n\n"
            f"Repartition par code de statut :\n{status_lines}\n\n"
            f"Top IPs :\n{top_lines}"
        )

        max_count = max(summary.hourly_counts) or 1
        hourly_lines = "\n".join(
            f"  {hour:>2}h  {'#' * int((count / max_count) * _BAR_WIDTH):<{_BAR_WIDTH}}  {count}"
            for hour, count in enumerate(summary.hourly_counts)
        )
        self.query_one("#stats-hourly", Static).update(f"Repartition horaire (UTC) :\n{hourly_lines}")
