"""Ecran Deception - equivalent TUI de `omega-serv deception
list/release`. `is_assignment_active` (domaine, pas d'I/O) determine la
colonne "Etat" - meme regle que le CLI (`list_active()` retourne aussi
les affectations expirees, jamais liberees)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.active_defense.manage_deception import release_deception
from omega_serv.domain.security.active_defense.policies import is_assignment_active
from omega_serv.interfaces.tui.screens._active_defense_collaborators_cache import (
    ActiveDefenseCollaboratorsCacheMixin,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class DeceptionScreen(ActiveDefenseCollaboratorsCacheMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._reset_active_defense_cache()
        self._selected_subject_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("DECEPTION", classes="omega-title")
            yield Static("", id="deception-error", classes="omega-hint")
            yield DataTable(id="deception-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Liberer", id="release", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#deception-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Source", "Profil", "Etat", "Affecte le", "Expire le")
        self._refresh()

    def _refresh(self) -> None:
        self._selected_subject_id = None
        self.query_one("#release", Button).disabled = True
        error_widget = self.query_one("#deception-error", Static)
        table = self.query_one("#deception-table", DataTable)
        table.clear()
        active_defense = self._active_defense_or_none()
        if active_defense is None:
            error_widget.update(self._active_defense_error or "")
            return
        error_widget.update("")
        now = self._container.clock.now()
        for assignment in active_defense.deception_assignment_repository.list_active():
            status = "active" if is_assignment_active(assignment, now) else "expiree"
            table.add_row(
                assignment.subject_id, assignment.profile_name, status,
                assignment.assigned_at.isoformat(), assignment.expires_at.isoformat(),
                key=assignment.subject_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_subject_id = str(event.row_key.value)
        self.query_one("#release", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "release" and self._selected_subject_id is not None:
            self.app.push_screen(
                ConfirmScreen(
                    title="LIBERER L'AFFECTATION",
                    message=f"Confirmer la liberation du leurre pour {self._selected_subject_id!r} ?",
                ),
                self._release,
            )

    def _release(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_subject_id is None:
            return
        active_defense = self._active_defense_or_none()
        if active_defense is None:
            return
        release_deception(active_defense.deception_assignment_repository, self._selected_subject_id)
        self.app.notify(f"Affectation de leurre liberee pour {self._selected_subject_id!r}.")
        self._refresh()
