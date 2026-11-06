"""Active Securite -> INTERVENTION MANUELLE -> Debannir (decision utilisateur 2026-11-06) : ne montre et ne leve QUE
les bans poses par Bannir (champ `origin` = intervention). Les autres se levent la ou ils ont ete poses : WAF ->
Modules (reseaux, auto-bans, CLI, omega-jail), RIPOSTE -> Actions."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.security.manual_intervention import manual_bans, unban_address
from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.blocklist import is_expired
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._intervention_access import (
    BlocklistUnavailable,
    open_blocklist,
)
from omega_serv.interfaces.tui.screens._riposte_access import cell, local_time, show
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _when(moment: str | None) -> str:
    if moment is None:
        return _("permanent")
    try:
        return local_time(datetime.fromisoformat(moment), short=True)
    except ValueError:
        return moment


class ManualUnbanScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("DÉBANNIR UNE ADRESSE IP"), classes="omega-title")
            yield Static(
                _("Seuls les bans posés par l'intervention manuelle apparaissent ici. Les autres se lèvent là où ils "
                  "ont été posés : WAF → Modules (réseaux, auto-bans, omega-jail), RIPOSTE → Actions."),
                classes="omega-hint",
            )
            yield Static("", id="unban-error", classes="omega-hint")
            yield DataTable(id="unban-table", classes="omega-riposte-table")
            yield Static("", id="unban-empty", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Lever"), id="unban", variant="error", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rafraîchir"), id="refresh")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#unban-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Adresse IP"), _("Motif du ban"), _("Posé le"), _("Expiration"), _("État"))
        self._refresh()

    def _refresh(self) -> None:
        self._select(None)
        table = self.query_one("#unban-table", DataTable)
        table.clear()
        try:
            _config, port = open_blocklist(self._container)
            entries = manual_bans(port)
        except BlocklistUnavailable as problem:
            show(self.query_one("#unban-error", Static), str(problem))
            return
        except OSError as e:
            show(self.query_one("#unban-error", Static),
                 _("Blocklist illisible ou non modifiable : {error}").format(error=e))
            return
        show(self.query_one("#unban-error", Static), "")
        now = self._container.clock.now()
        for entry in entries:
            table.add_row(
                cell(entry.network.split("/")[0]), cell(entry.reason), cell(_when(entry.created_at)),
                cell(_when(entry.expires_at)), cell(_("expiré") if is_expired(entry, now) else _("en vigueur")),
                key=entry.network,
            )
        show(self.query_one("#unban-empty", Static), "" if entries else _("Aucun ban posé par l'intervention manuelle."))

    def _select(self, network: str | None) -> None:
        self._selected = network
        self.query_one("#unban", Button).disabled = network is None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select(str(event.row_key.value))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value is not None:
            self._select(str(event.row_key.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "refresh":
            self._refresh()
        elif event.button.id == "unban" and self._selected is not None:
            network = self._selected
            self.app.push_screen(
                ConfirmScreen(title=_("Lever le ban"),
                              message=_("Lever le ban de {ip} ? Elle pourra de nouveau accéder au site.").format(
                                  ip=network.split("/")[0])),
                lambda confirmed: self._unban(network) if confirmed else None,
            )

    def _unban(self, network: str) -> None:
        try:
            _config, port = open_blocklist(self._container)
        except BlocklistUnavailable as problem:
            show(self.query_one("#unban-error", Static), str(problem))
            return
        result = unban_address(port, network)
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._refresh()
