"""Ecran "Voir et traiter IP" (gestion des logs, refonte menu
2026-10-15, OMEGA-LOG_PLAN §2/§3/§7) - REMPLACE `top_ips_screen.py` :
generalise le top N a N'IMPORTE QUEL(S) log(s) de la Bibliotheque
(plus seulement l'access log fixe d'Omega-Serv), via le parseur
generique (`domain/logs/parser.py`) et `application/logs/top_ips.py`.
Le retrait d'IP (`container.remove_ip_from_log`) existait DEJA dans
Omega-Serv - corrige en meme temps pour etre generique lui aussi (voir
`infrastructure/logging/logs_maintenance.py`), jamais re-ecrit ici.

Selection des logs par NUMEROS separes par des virgules - meme
convention que `log_view_screen.py`. Periode "Tout" AJOUTEE (absente de
l'ancien ecran, qui ne proposait que 24h/7j/30j)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.logs.library import list_library
from omega_serv.application.logs.top_ips import compute_top_ips_for_paths
from omega_serv.domain.logs.library import LogFile
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_PERIODS: tuple[tuple[str, str | None], ...] = (
    ("24h", "24h"), ("7d", "7d"), ("30d", "30d"), ("all", None),
)
_PERIOD_LABELS: dict[str, str] = {"24h": "24 heures", "7d": "7 jours", "30d": "30 jours", "all": "Tout"}


class ProcessIpScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._entries: list[LogFile] = []
        self._current_paths: list[str] = []
        self._selected_ip: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("VOIR ET TRAITER IP", classes="omega-title")
            yield DataTable(id="library-table")
            yield Static("Logs a analyser (numeros ci-dessus, separes par des virgules)", classes="omega-subtitle")
            yield Input(placeholder="ex: 1,2", id="selection-input")
            with Horizontal(classes="omega-actions"):
                for period_id, _period in _PERIODS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(_PERIOD_LABELS[period_id], id=f"period-{period_id}")
            yield Static("", id="ip-error", classes="omega-hint")
            yield DataTable(id="top-ips-table")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retirer cette IP des logs analyses", id="remove-ip", variant="error", disabled=True)
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#library-table", DataTable).cursor_type = "row"
        self.query_one("#library-table", DataTable).add_columns("#", "Chemin")
        self.query_one("#top-ips-table", DataTable).cursor_type = "row"
        self.query_one("#top-ips-table", DataTable).add_columns("IP", "Occurrences")
        self._entries = list_library(self._container.build_log_library_repository())
        table = self.query_one("#library-table", DataTable)
        for idx, entry in enumerate(self._entries, start=1):
            table.add_row(str(idx), entry.path)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "top-ips-table":
            return
        self._selected_ip = str(event.row_key.value)
        self.query_one("#remove-ip", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
            return
        if button_id.startswith("period-"):
            period = dict(_PERIODS)[button_id.removeprefix("period-")]
            self._compute(period)
            return
        if button_id == "remove-ip":
            self._remove_selected_ip()

    def _selected_paths(self) -> list[str] | None:
        error_widget = self.query_one("#ip-error", Static)
        raw = self.query_one("#selection-input", Input).value.strip()
        if not raw:
            error_widget.update("Saisissez au moins un numero de ligne.")
            return None
        paths: list[str] = []
        for token in raw.split(","):
            token = token.strip()
            if not token.isdigit() or not (1 <= int(token) <= len(self._entries)):
                error_widget.update(f"Numero invalide : {token!r}.")
                return None
            paths.append(self._entries[int(token) - 1].path)
        error_widget.update("")
        return paths

    def _compute(self, period: str | None) -> None:
        paths = self._selected_paths()
        if paths is None:
            return
        self._current_paths = paths
        top_ips = compute_top_ips_for_paths(paths, period=period, n=10)

        table = self.query_one("#top-ips-table", DataTable)
        table.clear()
        self._selected_ip = None
        self.query_one("#remove-ip", Button).disabled = True
        for top_ip in top_ips:
            table.add_row(top_ip.ip, str(top_ip.count), key=top_ip.ip)
        if not top_ips:
            self.app.notify("Aucune IP trouvee dans les log(s) selectionne(s) pour cette periode.")

    def _remove_selected_ip(self) -> None:
        if self._selected_ip is None or not self._current_paths:
            return
        ip = self._selected_ip
        self.app.push_screen(
            ConfirmScreen(
                title="RETIRER CETTE IP ?",
                message=f"Retirer toutes les lignes contenant {ip} de {len(self._current_paths)} fichier(s).",
            ),
            lambda confirmed: self._remove_if_confirmed(confirmed, ip),
        )

    def _remove_if_confirmed(self, confirmed: bool | None, ip: str) -> None:
        if not confirmed:
            return
        total = 0
        for path in self._current_paths:
            total += self._container.remove_ip_from_log(ip, Path(path))
        self.app.notify(f"{total} occurrence(s) de {ip} retiree(s) au total.")
        self._compute(None)
