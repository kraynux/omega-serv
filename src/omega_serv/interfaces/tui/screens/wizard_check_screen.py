# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant premier lancement, etape 6/8 - verification automatique
(structurelle puis environnement, meme deux couches que ConfigCheckScreen)
avant de pouvoir continuer : les portes bloquantes eventuelles restent
toujours affichees, jamais masquees (plan interface §11 etape 6). Les
memes 2 confirmations que la CLI (`--confirm-self-signed-public-bind`/
`--confirm-auth-without-tls`) sont proposees ici plutot que forcees."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Static

from omega_serv.domain.config.validation import validate_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_summary_screen import WizardSummaryScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens.wizard_state import WizardState


class WizardCheckScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, state: WizardState) -> None:
        super().__init__()
        self._container = container
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ETAPE 6/8 : VERIFICATION DE LA CONFIGURATION", classes="omega-title")
            yield Static("", id="check-result")
            yield Checkbox("Confirmer : bind public + certificat auto-signe", id="confirm-self-signed")
            yield Checkbox("Confirmer : authentification sans TLS", id="confirm-auth-without-tls")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Verifier", id="check", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Suivant", id="next", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Precedent", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._run_check()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "check":
            self._run_check()
            return
        if event.button.id == "next":
            self.app.push_screen(WizardSummaryScreen(container=self._container, state=self._state))

    def _run_check(self) -> None:
        result_widget = self.query_one("#check-result", Static)
        next_button = self.query_one("#next", Button)

        structural_errors = validate_config(self._state.config)
        if structural_errors:
            result_widget.update("Erreur de validation :\n" + "\n".join(f"  - {e}" for e in structural_errors))
            next_button.disabled = True
            return

        self._state.self_signed_public_bind_confirmed = self.query_one("#confirm-self-signed", Checkbox).value
        self._state.auth_without_tls_confirmed = self.query_one("#confirm-auth-without-tls", Checkbox).value

        runner = self._container.config_check_runner
        if runner is None:
            result_widget.update("Configuration valide (verification d'environnement indisponible).")
            next_button.disabled = False
            return

        env_errors = runner(
            self._state.config, self._container.filesystem, self._container.project_root,
            self._state.self_signed_public_bind_confirmed, self._state.auth_without_tls_confirmed,
        )
        if env_errors:
            result_widget.update("Erreur d'environnement :\n" + "\n".join(f"  - {e}" for e in env_errors))
            next_button.disabled = True
            return
        result_widget.update("Configuration valide.")
        next_button.disabled = False
