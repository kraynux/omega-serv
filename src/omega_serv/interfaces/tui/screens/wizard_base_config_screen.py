"""Assistant premier lancement, etape 4/8 - configuration de base : bind/
port uniquement (plan interface §11 etape 4), le reste des reglages
reste aux valeurs du profil choisi a l'etape precedente. Meme validation
structurelle pure que BaseConfigScreen (domain/config/validation.py),
mais applique a la configuration candidate en memoire, jamais ecrite ici."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.domain.config.validation import validate_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_tls_screen import WizardTlsScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens.wizard_state import WizardState


class WizardBaseConfigScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, state: WizardState) -> None:
        super().__init__()
        self._container = container
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static("ETAPE 4/8 : CONFIGURATION DE BASE", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("Adresse d'ecoute (server.bind)", classes="omega-subtitle")
            yield Input(value=self._state.config.server.bind, id="bind-input")
            yield Static("Port (server.port)", classes="omega-subtitle")
            yield Input(value=str(self._state.config.server.port), id="port-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Suivant", id="next", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Precedent", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "next":
            self._next()

    def _next(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        port_text = self.query_one("#port-input", Input).value.strip()
        try:
            port = int(port_text)
        except ValueError:
            error_widget.update(f"Port invalide (nombre attendu) : {port_text!r}")
            return

        new_server = replace(
            self._state.config.server,
            bind=self.query_one("#bind-input", Input).value.strip(),
            port=port,
        )
        new_config = replace(self._state.config, server=new_server)

        errors = validate_config(new_config)
        if errors:
            error_widget.update("Erreur de validation :\n" + "\n".join(f"  - {e}" for e in errors))
            return

        self._state.config = new_config
        error_widget.update("")
        self.app.push_screen(WizardTlsScreen(container=self._container, state=self._state))
