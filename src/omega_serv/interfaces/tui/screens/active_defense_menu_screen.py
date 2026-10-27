"""Ecran Active Securite (retour utilisateur 2026-09-12, renomme et
restructure le 2026-09-13 : "ACTIVE DEFENSE" devient "ACTIVE SECURITE",
regroupe DEUX containers - Active Defense et WAF (deplace hors de
"Configuration detaillee du serveur", menu 3), cote a cote (retour
utilisateur 2026-10-10 : "que cela puisse etre lisible" - deux panneaux
`.omega-home-menu` de largeur `auto` dans un `Horizontal`, chacun garde
sa propre hauteur selon son nombre de boutons). Meme raison pour les
deux : ils exposent surtout de l'etat OPERATIONNEL qui change en continu
(menaces/incidents/affectations de leurre pour l'un, mode/packs charges/
blocklist/magnet pour l'autre), plus proche d'Audit de securite ou Etat
& Ressources qu'un simple formulaire de configuration statique - WAF n'a
plus sa place a cote d'alias/redirections/TLS.

"Magnet" (retour utilisateur 2026-10-10) ajoute en 5e item WAF, apres
"Custom" : importer un script WAF `mod_magnet` Lighttpd externe sans le
reecrire (voir waf_magnet_screen.py) - assez different des 3 autres
(etat/reglages passifs/test) et du formulaire "Custom" (ecrit une regle
DANS le moteur natif) pour justifier son propre ecran plutot que d'etre
ajoute a Modules.

"Exclusions et debit" (OMEGA-SERV_ETUDE_RATE_LIMIT_EXCLUSIONS.md, lot 3)
juste sous Modules : regles de debit par dossier/IP-reseau et exclusions
d'inspection (waf_rate_limit_screen.py)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.i18n import _
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
from omega_serv.interfaces.tui.screens.waf_magnet_screen import WafMagnetScreen
from omega_serv.interfaces.tui.screens.waf_modules_screen import WafModulesScreen
from omega_serv.interfaces.tui.screens.waf_rate_limit_screen import WafRateLimitScreen
from omega_serv.interfaces.tui.screens.waf_status_screen import WafStatusScreen
from omega_serv.interfaces.tui.screens.waf_test_screen import WafTestScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_ACTIVE_DEFENSE_ITEMS: tuple[tuple[str, str], ...] = (
    ("status", _("État")),
    ("settings", _("Réglages")),
    ("threats", _("Menaces")),
    ("incidents", _("Incidents")),
    ("deception", _("Deception")),
    ("simulate", _("Simuler")),
)

_WAF_ITEMS: tuple[tuple[str, str], ...] = (
    ("waf-status", _("État")),
    ("waf-modules", _("Modules")),
    ("waf-rate-limit", _("Exclusions et débit")),
    ("waf-test", _("Tester")),
    ("waf-custom", _("Custom")),
    ("waf-magnet", _("Magnet")),
)


class ActiveDefenseMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            with Center():
                yield Static(_("ACTIVE SÉCURITÉ"), classes="omega-title")
            if is_missing_live_group(DEFAULT_SYSTEM_GROUP):
                with Center():
                    yield Static(
                        _("Le service système dédié ({DEFAULT_SYSTEM_GROUP!r}) est installé, mais cette session n'a pas encore pris en compte votre appartenance à ce groupe - deconnectez-vous/reconnectez-vous (ou 'newgrp ").format(DEFAULT_SYSTEM_GROUP=DEFAULT_SYSTEM_GROUP) + DEFAULT_SYSTEM_GROUP + _("') "
                        "avant d'utiliser les sous-écrans ci-dessous, sinon ils resteront en erreur "
                        "d'accès."),
                        id="group-mismatch-hint",
                        classes="omega-hint",
                    )
            with Center(), Horizontal(classes="omega-panel-row"):
                with Vertical(classes="omega-home-menu") as active_defense_menu:
                    for item_id, label in _ACTIVE_DEFENSE_ITEMS:
                        with Container(classes="omega-btn-frame"):
                            yield Button(label, id=item_id)
                    active_defense_menu.border_title = _("ACTIVE DEFENSE")
                with Vertical(classes="omega-home-menu") as waf_menu:
                    for item_id, label in _WAF_ITEMS:
                        with Container(classes="omega-btn-frame"):
                            yield Button(label, id=item_id)
                    waf_menu.border_title = _("WAF")
            with Center(), Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
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
        if item_id == "waf-rate-limit":
            return WafRateLimitScreen(container=self._container)
        if item_id == "waf-test":
            return WafTestScreen(container=self._container)
        if item_id == "waf-custom":
            return WafCustomRuleScreen(container=self._container)
        if item_id == "waf-magnet":
            return WafMagnetScreen(container=self._container)
        return None
