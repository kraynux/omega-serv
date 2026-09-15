# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant premier lancement, etape 3/8 - choix du profil de base
(plan interface §11 etape 3 : minimal/standard/hardened/development,
description affichee pour chacun). Reutilise
application/config/apply_profile.py::plan_profile_application (aucune
nouvelle logique metier) - calcule sur les valeurs par defaut
(`domain/config/defaults.py::builtin_safe_defaults`), jamais sur un
fichier de configuration existant (l'assistant n'en suppose aucun)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.apply_profile import plan_profile_application
from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_base_config_screen import WizardBaseConfigScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens.wizard_state import WizardState


class WizardProfileScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, state: WizardState) -> None:
        super().__init__()
        self._container = container
        self._state = state
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ETAPE 3/8 : CHOIX DU PROFIL DE BASE", classes="omega-title")
            yield DataTable(id="profiles-table")
            yield Static("Selectionnez un profil pour voir son detail.", id="profile-detail", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Suivant", id="next", variant="primary", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Precedent", id="back")
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
            self.query_one("#next", Button).disabled = True
            return
        self.query_one("#profile-detail", Static).update(f"[b]{profile.name}[/b]\n{profile.description}")
        self.query_one("#next", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "next" and self._selected_name is not None:
            self._next()

    def _next(self) -> None:
        assert self._selected_name is not None
        profile = self._container.profiles.load_profile(self._selected_name)
        plan = plan_profile_application(self._state.config, profile)
        self._state.profile_name = self._selected_name
        self._state.config = plan.new_config
        self.app.push_screen(WizardBaseConfigScreen(container=self._container, state=self._state))
