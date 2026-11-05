"""RIPOSTE - Simuler (topo §6.4-5, plan §3.10 ; lot 5) : une situation saisie (IP, classe d'attaque, niveau
Active Defense, nombre de retours, visites de leurre) -> decision expliquee avec la configuration reelle
(politique retenue, exclusions verifiees, action, duree, ou raison du refus). Rien n'est applique ni ecrit.

Ou un evenement recent : les dernieres decisions du processus, chacune avec son explication."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from omega_serv.application.riposte.console import simulate_situation
from omega_serv.core.i18n import _
from omega_serv.domain.security.active_defense.value_objects import KNOWN_ATTACK_CLASSES
from omega_serv.domain.security.riposte.config import KNOWN_AD_LEVELS
from omega_serv.interfaces.cli.riposte_text import format_decision, status_label
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._riposte_access import (
    RiposteAccessMixin,
    StoreUnavailable,
    cell,
    local_time,
    show,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.security.riposte.decide import Decision

RECENT_LIMIT = 50
_LEVEL_ORDER = ("normal", "suspicious", "hostile", "contained")


def _whole(text: str) -> int | None:
    text = text.strip() or "0"
    return int(text) if text.isdigit() else None


class RiposteSimulateScreen(RiposteAccessMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._recent: list[Decision] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RIPOSTE - SIMULER"), classes="omega-title")
            yield Static(_("Décision expliquée avec la configuration réelle : rien n'est appliqué ni écrit."),
                         classes="omega-hint")
            yield Static(_("Adresse IP de la source"), classes="omega-subtitle")
            yield Input(value="203.0.113.42", id="sim-ip")
            yield Static(_("Classe d'attaque"), classes="omega-subtitle")
            yield Select([(name, name) for name in sorted(KNOWN_ATTACK_CLASSES)], value="scan", allow_blank=False,
                         id="sim-class")
            yield Static(_("Niveau Active Defense atteint pendant l'épisode en cours"), classes="omega-subtitle")
            yield Select([(_("non renseigné"), ""), *((level, level) for level in _LEVEL_ORDER if level in KNOWN_AD_LEVELS)],
                         value="", allow_blank=False, id="sim-level")
            yield Static(_("Nombre d'épisodes (retours), celui en cours compris"), classes="omega-subtitle")
            yield Input(value="1", id="sim-returns")
            yield Static(_("Visites de leurre pendant l'épisode en cours"), classes="omega-subtitle")
            yield Input(value="0", id="sim-decoy-hits")
            yield Static("", id="simulate-result")
            yield Static(_("Décisions récentes du processus"), classes="omega-subtitle")
            yield Static("", id="recent-error", classes="omega-hint")
            yield DataTable(id="recent-table", classes="omega-riposte-table")
            yield Static("", id="recent-detail", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Simuler"), id="simulate", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#recent-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Quand"), _("Source"), _("Décision"), _("Politique"))
        self._load_recent()

    def _load_recent(self) -> None:
        config = self._load_riposte_config()
        if config is None:
            return
        table = self.query_one("#recent-table", DataTable)
        table.clear()
        try:
            with self._riposte_store(config) as store:
                rows = store.list_decisions(RECENT_LIMIT)
        except StoreUnavailable as error:
            show(self.query_one("#recent-error", Static), str(error))
            return
        show(self.query_one("#recent-error", Static), "" if rows else _("Aucune décision enregistrée."))
        self._recent = [decision for decision, _applied in rows]
        for index, decision in enumerate(self._recent):
            table.add_row(cell(local_time(decision.decided_at)), cell(decision.ip), cell(status_label(decision.status)),
                          cell(decision.policy_id or "-"), key=str(index))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        decision = self._recent[int(str(event.row_key.value))]
        show(self.query_one("#recent-detail", Static), "\n".join(format_decision(decision)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "simulate":
            self._simulate()

    def _simulate(self) -> None:
        result = self.query_one("#simulate-result", Static)
        returns = _whole(self.query_one("#sim-returns", Input).value)
        decoy_hits = _whole(self.query_one("#sim-decoy-hits", Input).value)
        if returns is None or decoy_hits is None:
            show(result, _("Nombre invalide (entier positif attendu)."))
            return
        config = self._load_riposte_config()
        if config is None:
            return
        level = str(self.query_one("#sim-level", Select).value) or None
        decision = simulate_situation(
            config, ip=self.query_one("#sim-ip", Input).value.strip() or "203.0.113.42",
            attack_class=str(self.query_one("#sim-class", Select).value), level=level,
            returns=returns, decoy_hits=decoy_hits, now=self._container.clock.now(),
        )
        show(result, "\n".join([_("Simulation (rien n'est appliqué) :"), *format_decision(decision)]))
        result.scroll_visible()
