"""Ecran Active Securite (retour utilisateur 2026-09-12, renomme et
restructure le 2026-09-13 : "ACTIVE DEFENSE" devient "ACTIVE SECURITE",
regroupe DEUX containers - Active Defense (inchange) et, en dessous, WAF
(deplace hors de "Configuration detaillee du serveur", menu 3). Meme
raison pour les deux : ils exposent surtout de l'etat OPERATIONNEL qui
change en continu (menaces/incidents/affectations de leurre pour l'un,
mode/packs charges/blocklist pour l'autre), plus proche d'Audit de
securite ou Etat & Ressources qu'un simple formulaire de configuration
statique - WAF n'a plus sa place a cote d'alias/redirections/TLS."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.platform_info import is_missing_live_group
from omega_serv.domain.services.systemd_unit import DEFAULT_SYSTEM_GROUP
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.active_defense_settings_screen import (
    ActiveDefenseSettingsScreen,
)
from omega_serv.interfaces.tui.screens.active_defense_simulate_screen import (
    ActiveDefenseSimulateScreen,
)
from omega_serv.interfaces.tui.screens.active_defense_status_screen import ActiveDefenseStatusScreen
from omega_serv.interfaces.tui.screens.deception_screen import DeceptionScreen
from omega_serv.interfaces.tui.screens.incidents_screen import IncidentsScreen
from omega_serv.interfaces.tui.screens.threats_screen import ThreatsScreen
from omega_serv.interfaces.tui.screens.waf_custom_rule_screen import WafCustomRuleScreen
from omega_serv.interfaces.tui.screens.waf_modules_screen import WafModulesScreen
from omega_serv.interfaces.tui.screens.waf_status_screen import WafStatusScreen
from omega_serv.interfaces.tui.screens.waf_test_screen import WafTestScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_ACTIVE_DEFENSE_ITEMS: tuple[tuple[str, str], ...] = (
    ("status", "Etat"),
    ("settings", "Reglages"),
    ("threats", "Menaces"),
    ("incidents", "Incidents"),
    ("deception", "Deception"),
    ("simulate", "Simuler"),
)

_WAF_ITEMS: tuple[tuple[str, str], ...] = (
    ("waf-status", "Etat"),
    ("waf-modules", "Modules"),
    ("waf-test", "Tester"),
    ("waf-custom", "Custom"),
)


class ActiveDefenseMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            with Center():
                yield Static("ACTIVE SECURITE", classes="omega-title")
            if is_missing_live_group(DEFAULT_SYSTEM_GROUP):
                with Center():
                    yield Static(
                        f"Le service systeme dedie ({DEFAULT_SYSTEM_GROUP!r}) est installe, mais cette "
                        "session n'a pas encore pris en compte votre appartenance a ce groupe - "
                        "deconnectez-vous/reconnectez-vous (ou 'newgrp " + DEFAULT_SYSTEM_GROUP + "') "
                        "avant d'utiliser les sous-ecrans ci-dessous, sinon ils resteront en erreur "
                        "d'acces.",
                        id="group-mismatch-hint",
                        classes="omega-hint",
                    )
            with Center(), Vertical(classes="omega-home-menu") as active_defense_menu:
                for item_id, label in _ACTIVE_DEFENSE_ITEMS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
                active_defense_menu.border_title = "ACTIVE DEFENSE"
            with Center(), Vertical(classes="omega-home-menu") as waf_menu:
                for item_id, label in _WAF_ITEMS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
                waf_menu.border_title = "WAF"
            with Center(), Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        screen = self._screen_for(event.button.id)
        if screen is not None:
            self.app.push_screen(screen)

    def _screen_for(self, item_id: str | None) -> Screen[None] | None:
        if item_id == "status":
            return ActiveDefenseStatusScreen(container=self._container)
        if item_id == "settings":
            return ActiveDefenseSettingsScreen(container=self._container)
        if item_id == "threats":
            return ThreatsScreen(container=self._container)
        if item_id == "incidents":
            return IncidentsScreen(container=self._container)
        if item_id == "deception":
            return DeceptionScreen(container=self._container)
        if item_id == "simulate":
            return ActiveDefenseSimulateScreen(container=self._container)
        if item_id == "waf-status":
            return WafStatusScreen(container=self._container)
        if item_id == "waf-modules":
            return WafModulesScreen(container=self._container)
        if item_id == "waf-test":
            return WafTestScreen(container=self._container)
        if item_id == "waf-custom":
            return WafCustomRuleScreen(container=self._container)
        return None
