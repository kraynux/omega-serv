"""Ecran Top IPs du log d'acces (plan interface §3.4/§8) - table complete
de `LogStatsSummary.top_ips`, avec retrait d'une IP du log via
`container.remove_ip_from_log` (action destructive donc confirmation
obligatoire, meme patron que `purge_log_archives_screen.py`)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_PERIODS: tuple[tuple[str, str], ...] = (
    ("24h", "24 heures"),
    ("7d", "7 jours"),
    ("30d", "30 jours"),
)


class TopIpsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._period = "24h"
        self._selected_ip: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("TOP IPS DU LOG D'ACCES", classes="omega-title")
            yield Static("", id="top-ips-error", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                for period_id, label in _PERIODS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=f"period-{period_id}")
            yield DataTable(id="top-ips-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Retirer cette IP des logs", id="remove-ip", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#top-ips-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("IP", "Requetes", "Vu la derniere fois")
        self._refresh()

    def _access_log_path(self) -> Path | None:
        error_widget = self.query_one("#top-ips-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return None
        error_widget.update("")
        return self._container.project_root / load_result.config.logs.access

    def _refresh(self) -> None:
        log_path = self._access_log_path()
        table = self.query_one("#top-ips-table", DataTable)
        table.clear()
        self._selected_ip = None
        self.query_one("#remove-ip", Button).disabled = True
        if log_path is None:
            return

        summary = self._container.compute_log_stats(log_path, self._period)
        for ip_stat in summary.top_ips:
            table.add_row(ip_stat.ip, str(ip_stat.count), ip_stat.last_seen.isoformat(), key=ip_stat.ip)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_ip = str(event.row_key.value)
        self.query_one("#remove-ip", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
            return
        if button_id.startswith("period-"):
            self._period = button_id.removeprefix("period-")
            self._refresh()
            return
        if button_id == "remove-ip" and self._selected_ip is not None:
            self.app.push_screen(
                ConfirmScreen(
                    title="RETIRER L'IP DES LOGS",
                    message=f"Retirer toutes les entrees de {self._selected_ip} du log d'acces ?",
                ),
                self._remove_if_confirmed,
            )

    def _remove_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_ip is None:
            return
        log_path = self._access_log_path()
        if log_path is None:
            return
        removed = self._container.remove_ip_from_log(self._selected_ip, log_path)
        error_widget = self.query_one("#top-ips-error", Static)
        error_widget.update("")
        self.app.notify(f"{removed} entree(s) retiree(s) pour {self._selected_ip}.")
        self._refresh()
