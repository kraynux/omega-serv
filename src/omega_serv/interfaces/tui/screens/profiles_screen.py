"""Ecran Profils (plan interface §6, menu 2.1-2.3) : liste + detail +
lancement de l'application (le diff/la confirmation eux-memes vivent
dans apply_profile_screen.py, jamais melanges ici - meme separation que
la CLI `profile show` / `profile apply`)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.apply_profile_screen import ApplyProfileScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class ProfilesScreen(OmegaScreen):
    """Liste des profils (`profile list`), detail au clic (`profile
    show`), bouton "Appliquer" vers ApplyProfileScreen (`profile apply`)."""

    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("PROFILS", classes="omega-title")
            yield DataTable(id="profiles-table")
            yield Static("Selectionnez un profil pour voir son detail.", id="profile-detail", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Appliquer", id="apply", variant="primary", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#profiles-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Nom")
        for name in sorted(self._container.profiles.list_profile_names()):
            table.add_row(name, key=name)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        name = str(event.row_key.value)
        self._selected_name = name
        try:
            profile = self._container.profiles.load_profile(name)
        except (ProfileNotFoundError, ProfileLoadError) as exc:
            self.query_one("#profile-detail", Static).update(f"Erreur : {exc}")
            self.query_one("#apply", Button).disabled = True
            return
        self.query_one("#profile-detail", Static).update(f"[b]{profile.name}[/b]\n{profile.description}")
        self.query_one("#apply", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "apply" and self._selected_name is not None:
            self.app.push_screen(ApplyProfileScreen(container=self._container, profile_name=self._selected_name))
