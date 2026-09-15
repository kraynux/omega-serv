# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant premier lancement, etape 7/8 - resume final (meme diff que
spec §9.2, entre les valeurs par defaut et la configuration composee par
l'assistant) + confirmation d'ecriture (plan interface §11). L'ecriture
elle-meme passe par `container.configuration.save()`, qui sauvegarde deja
tout fichier existant avant ecrasement (JsonConfigRepository, comportement
etabli depuis la Phase 0) - aucune logique de sauvegarde supplementaire
necessaire ici meme si un `config/omega-serve.json` preexistait."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.domain.config.defaults import builtin_safe_defaults
from omega_serv.domain.config.diff import diff_configs
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_service_screen import WizardServiceScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens.wizard_state import WizardState


class WizardSummaryScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, state: WizardState) -> None:
        super().__init__()
        self._container = container
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("ETAPE 7/8 : RESUME", classes="omega-title")
            yield Static("", id="summary-diff")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ecrire la configuration", id="write", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Precedent", id="back")
        yield Footer()

    def on_mount(self) -> None:
        changes = diff_configs(builtin_safe_defaults().to_dict(), self._state.config.to_dict())
        if not changes:
            self.query_one("#summary-diff", Static).update("Aucune difference avec les valeurs par defaut.")
            return
        self.query_one("#summary-diff", Static).update(
            f"Profil : {self._state.profile_name or '(aucun)'}\n\nModifications :\n"
            + "\n".join(str(change) for change in changes)
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "write":
            self._write()

    def _write(self) -> None:
        self._container.configuration.save(self._container.config_file, self._state.config)
        self.app.notify(f"Configuration ecrite dans {self._container.config_file}.")
        self.app.push_screen(WizardServiceScreen(container=self._container))
