# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Menaces - equivalent TUI de `omega-serv threats list/show`. Pas
de filtre par niveau dans cette V1 (la table entiere reste lisible en
un coup d'oeil pour le volume attendu, D-008 - le filtre CLI `--level`
reste disponible pour un usage scripte)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.active_defense.queries import list_threat_states
from omega_serv.interfaces.tui.screens._active_defense_collaborators_cache import (
    ActiveDefenseCollaboratorsCacheMixin,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class ThreatsScreen(ActiveDefenseCollaboratorsCacheMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._reset_active_defense_cache()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("MENACES SUIVIES", classes="omega-title")
            yield Static("", id="threats-error", classes="omega-hint")
            yield DataTable(id="threats-table")
            yield Static("", id="threat-detail", classes="omega-hint")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#threats-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Source", "Score", "Niveau", "Mise a jour", "Expiration")
        self._refresh()

    def _refresh(self) -> None:
        error_widget = self.query_one("#threats-error", Static)
        active_defense = self._active_defense_or_none()
        if active_defense is None:
            error_widget.update(self._active_defense_error or "")
            return
        error_widget.update("")
        table = self.query_one("#threats-table", DataTable)
        table.clear()
        for state in list_threat_states(active_defense.threat_state_repository):
            table.add_row(
                state.subject_id, str(state.score), state.level,
                state.updated_at.isoformat(), state.expires_at.isoformat(),
                key=state.subject_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#threats-table", DataTable)
        row = table.get_row(event.row_key)
        subject_id, score, level, updated_at, expires_at = row
        self.query_one("#threat-detail", Static).update(
            f"Source : {subject_id}\nScore : {score}\nNiveau : {level}\n"
            f"Mise a jour : {updated_at}\nExpiration : {expires_at}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
