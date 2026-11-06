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
d'inspection (waf_rate_limit_screen.py) - libelle du bouton devenu
« Limitations » (RIPOSTE lot 5, topo §6.2 : plus court, couvre limite
globale, par dossier, par IP et exclusions ; le titre de l'ecran reste
complet).

RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md, lot 5) : 3e colonne, ordre
WAF -> ACTIVE DEFENSE -> RIPOSTE (proteger, detecter, riposter - le
parcours d'une attaque). Classe dediee `.omega-security-menu` (cadre de
bouton 20, padding reduit) pour tenir en 80 colonnes ; les autres menus
gardent leur cadre de 32."""
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
from omega_serv.interfaces.tui.screens.ban_status_screen import BanStatusScreen
from omega_serv.interfaces.tui.screens.deception_screen import DeceptionScreen
from omega_serv.interfaces.tui.screens.incidents_screen import IncidentsScreen
from omega_serv.interfaces.tui.screens.manual_ban_screen import ManualBanScreen
from omega_serv.interfaces.tui.screens.manual_unban_screen import ManualUnbanScreen
from omega_serv.interfaces.tui.screens.riposte_actions_screen import RiposteActionsScreen
from omega_serv.interfaces.tui.screens.riposte_policies_screen import RipostePoliciesScreen
from omega_serv.interfaces.tui.screens.riposte_recidives_screen import RiposteRecidivesScreen
from omega_serv.interfaces.tui.screens.riposte_settings_screen import RiposteSettingsScreen
from omega_serv.interfaces.tui.screens.riposte_simulate_screen import RiposteSimulateScreen
from omega_serv.interfaces.tui.screens.riposte_status_screen import RiposteStatusScreen
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
    ("waf-rate-limit", _("Limitations")),
    ("waf-test", _("Tester")),
    ("waf-custom", _("Custom")),
    ("waf-magnet", _("Magnet")),
)

_RIPOSTE_ITEMS: tuple[tuple[str, str], ...] = (
    ("riposte-status", _("État")),
    ("riposte-policies", _("Politiques")),
    ("riposte-actions", _("Actions")),
    ("riposte-recidives", _("Récidives")),
    ("riposte-simulate", _("Simuler")),
    ("riposte-settings", _("Réglages")),
)


# INTERVENTION MANUELLE (decisions utilisateur 2026-11-06) : 4e cadre, une ligne sous les trois colonnes et de leur
# largeur, au-dessus de Retour. Ban sans condition d'une adresse IP dans la blocklist du WAF, sans lien avec Active
# Defense ni RIPOSTE.
_INTERVENTION_ITEMS: tuple[tuple[str, str], ...] = (
    ("intervention-ban", _("Bannir")),
    ("intervention-unban", _("Débannir")),
    ("intervention-status", _("Statut des bans")),
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
                for title, items in ((_("WAF"), _WAF_ITEMS), (_("ACTIVE DEFENSE"), _ACTIVE_DEFENSE_ITEMS),
                                     (_("RIPOSTE"), _RIPOSTE_ITEMS)):
                    with Vertical(classes="omega-home-menu omega-security-menu") as menu:
                        for item_id, label in items:
                            with Container(classes="omega-btn-frame"):
                                yield Button(label, id=item_id)
                        menu.border_title = title
            with Center(), Horizontal(classes="omega-home-menu omega-intervention-menu") as intervention:
                for item_id, label in _INTERVENTION_ITEMS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
                intervention.border_title = _("INTERVENTION MANUELLE")
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
        intervention_screens: dict[str, type[OmegaScreen]] = {
            "intervention-ban": ManualBanScreen, "intervention-unban": ManualUnbanScreen,
            "intervention-status": BanStatusScreen,
        }
        if item_id in intervention_screens:
            return intervention_screens[item_id](container=self._container)  # type: ignore[call-arg]
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
        riposte_screens: dict[str, type[OmegaScreen]] = {
            "riposte-status": RiposteStatusScreen, "riposte-policies": RipostePoliciesScreen,
            "riposte-actions": RiposteActionsScreen, "riposte-recidives": RiposteRecidivesScreen,
            "riposte-simulate": RiposteSimulateScreen, "riposte-settings": RiposteSettingsScreen,
        }
        screen_class = riposte_screens.get(item_id or "")
        return None if screen_class is None else screen_class(container=self._container)  # type: ignore[call-arg]
