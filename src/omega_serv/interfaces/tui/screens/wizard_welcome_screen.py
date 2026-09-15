# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant premier lancement, etape 1/8 - bienvenue (plan interface
§11 etape 1) : point d'entree de l'assistant, ecran d'orchestration pure
qui enchaine les cas d'usage `application/` deja existants dans un ordre
guide, sans aucune logique metier nouvelle (README §1 : aucun module de
securite n'est active par defaut)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_capabilities_screen import WizardCapabilitiesScreen
from omega_serv.interfaces.tui.screens.wizard_state import WizardState

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class WizardWelcomeScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ASSISTANT PREMIER LANCEMENT", classes="omega-title")
            yield Static(
                "OMEGA-SERV sert des fichiers statiques et peut, sur option, activer "
                "un pare-feu applicatif (WAF), TLS, l'authentification et FastCGI/PHP-FPM.\n\n"
                "Aucun module de securite n'est active par defaut : cet assistant vous "
                "guide, etape par etape, jusqu'a une configuration ecrite et prete a "
                "servir. Rien n'est ecrit sur disque avant l'etape de resume final.",
                classes="omega-hint",
            )
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Commencer", id="next", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "next":
            self.app.push_screen(
                WizardCapabilitiesScreen(container=self._container, state=WizardState())
            )
