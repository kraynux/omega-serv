# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant premier lancement, etape 2/8 - registre des capacites en
lecture seule (plan interface §11 etape 2) : avertit si le port souhaite
est deja occupe ou si openssl est absent - deja couvert par les sondes
existantes (infrastructure/probe/scanner.py, Phase IV), rien de neuf a
detecter ici. Scanne avec le port par defaut (aucun profil ni port
personnalise n'est encore choisi a ce stade de l'assistant, cf. etapes
3/4) - purement informatif."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.capability_registry import CapabilityRegistry
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_profile_screen import WizardProfileScreen
from omega_serv.interfaces.tui.widgets.capabilities_table import CapabilitiesTable

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens.wizard_state import WizardState


class WizardCapabilitiesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, state: WizardState) -> None:
        super().__init__()
        self._container = container
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ETAPE 2/8 : REGISTRE DES CAPACITES (LECTURE SEULE)", classes="omega-title")
            yield CapabilitiesTable(id="capabilities-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Suivant", id="next", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Precedent", id="back")
        yield Footer()

    def on_mount(self) -> None:
        # Retour utilisateur (audit "gel d'ecran") : `scanner.scan()`
        # sonde reellement le port configure (connexion reseau) - tourne
        # en synchrone sur la boucle asyncio, gele l'interface le temps
        # de chaque sonde. Meme patron que capabilities_screen.py
        # (l'ecran non-assistant equivalent) : deporte dans un thread de
        # travail.
        self.query_one("#next", Button).disabled = True
        port = self._state.config.server.port
        self.run_worker(lambda: self._scan_in_thread(port), thread=True, exclusive=True)

    def _scan_in_thread(self, port: int) -> None:
        scanner = self._container.build_capability_scanner(port, None)
        registry = CapabilityRegistry(scanner.scan())
        self.app.call_from_thread(self._finish_scan, registry)

    def _finish_scan(self, registry: CapabilityRegistry) -> None:
        self.query_one("#next", Button).disabled = False
        self.query_one("#capabilities-table", CapabilitiesTable).set_capabilities(registry.list_all())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "next":
            self.app.push_screen(WizardProfileScreen(container=self._container, state=self._state))
