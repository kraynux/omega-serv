# Copyright (c) 2026 kraynux - [kraynux@proton.me](mailto:kraynux@proton.me) - Licence MIT (voir fichier LICENSE)
"""Ecran d'accueil : menu principal vers les autres ecrans. Adapte du
patron screens/home.py d'omega-check (plan interface §0/3.1) - menu
plat (un bouton par ecran reel), pas un menu numerote imbrique comme le
texte de la spec §8, plus simple a naviguer au clavier.

Peuple phase par phase (plan interface §12) - jamais un bouton avant que
son ecran cible existe reellement. Phase II (2026-09-08) : Profils,
Options, Service, Verifier la configuration, Simuler une requete, Audit
de securite, Configuration detaillee (menu 3). Phase IV (2026-09-08) :
Registre des capacites (menu 1, place en tete de liste). Phase V
(2026-09-08) : Gestion des logs (menu 4, voir/suivre un fichier + lnav -
"moitie 1" seulement, rotation/stats/top-IP restent Phase VI). Phase VI
(2026-09-08) : reste de la gestion des logs. Phase VII (2026-09-08) :
Sauvegarde de configuration. Phase VIII (2026-09-08) : Assistant premier
lancement (parcours central du plan §11, place tout en tete de liste).

**Options et Verifier la configuration retires d'ici (retour utilisateur
2026-09-09)** : juges redondants une fois le raccourci "OPTIONS ET
VERIFICATION" ajoute dans ServerConfigMenuScreen (menu 3) - meme
parcours utilisateur (ajuster des options detaillees puis verifier),
desormais accessible uniquement depuis la Configuration detaillee,
jamais depuis deux endroits differents du menu principal.

**"Simuler une requete" remplace ici par "Etat & Ressources" (retour
utilisateur 2026-09-09)** : la fonction elle-meme n'est PAS retiree,
juste deplacee - reintroduite comme bouton a l'interieur du nouvel
ecran (resource_status_screen.py::ResourceStatusScreen), qui offre un
apercu complet en un coup d'oeil (etat serveur/service, flux du log
d'acces, ressources systeme) - un point d'entree plus utile au
quotidien que l'ancien raccourci direct vers un outil de diagnostic
ponctuel."""
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header

from omega_serv.interfaces.tui.screens._base import show_contextual_help
from omega_serv.interfaces.tui.screens.active_defense_menu_screen import ActiveDefenseMenuScreen
from omega_serv.interfaces.tui.screens.audit_screen import AuditScreen
from omega_serv.interfaces.tui.screens.backup_screen import BackupScreen
from omega_serv.interfaces.tui.screens.capabilities_screen import CapabilitiesScreen
from omega_serv.interfaces.tui.screens.instances_screen import InstancesScreen
from omega_serv.interfaces.tui.screens.logs_menu_screen import LogsMenuScreen
from omega_serv.interfaces.tui.screens.profiles_screen import ProfilesScreen
from omega_serv.interfaces.tui.screens.quit_confirm import QuitConfirmScreen
from omega_serv.interfaces.tui.screens.resource_status_screen import ResourceStatusScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.service_screen import ServiceScreen
from omega_serv.interfaces.tui.screens.wizard_welcome_screen import WizardWelcomeScreen
from omega_serv.interfaces.tui.widgets.home_wordmark import HomeWordmark

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_MENU_ITEMS: tuple[tuple[str, str], ...] = (
    ("wizard", "Assistant premier lancement"),
    ("capabilities", "Registre des capacites"),
    ("profiles", "Profils"),
    ("server-config", "Configuration detaillee"),
    ("logs", "Gestion des logs"),
    ("service", "Service"),
    ("instances", "Multi-instance"),
    ("resource-status", "Etat & Ressources"),
    ("active-defense", "Active Securite"),
    ("audit", "Audit de securite"),
    ("backup", "Sauvegarde de configuration"),
)


class HomeScreen(Screen[None]):
    """Menu principal, racine de la pile de navigation. N'herite pas de
    OmegaScreen : `echap` ici demande confirmation de sortie, pas un
    dismiss() (rien "en dessous" de cet ecran)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Retour", show=True),
        Binding("f1", "show_help", "Aide de cet ecran", show=True),
    ]

    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        # Le cadre "application" (bordure/fond) vient de
        # styles/terminal_frame.tcss, applique directement a
        # `.omega-home-root` - jamais un Container supplementaire ici
        # (retour utilisateur 2026-09-13, voir ce fichier).
        with Vertical(classes="omega-home-root"):
            with Center():
                yield HomeWordmark()
            with Center():
                with Vertical(classes="omega-home-menu") as menu:
                    for item_id, label in _MENU_ITEMS:
                        with Container(classes="omega-btn-frame"):
                            yield Button(self._label_for(item_id, label).upper(), id=item_id)
                menu.border_title = "MENU PRINCIPAL"
        yield Footer()

    def _label_for(self, item_id: str, default_label: str) -> str:
        # Retour utilisateur (plan multi-instance §10) : le libelle
        # reflete automatiquement le nombre d'instances connues, jamais
        # un toggle explicite separe a retenir - "Multi-instance" reste
        # invisible-en-substance (zero changement percu) pour le cas
        # tres majoritaire (0/1 instance).
        if item_id != "instances":
            return default_label
        count = len(self._container.instance_registry.load())
        return f"Instances ({count})" if count >= 2 else default_label

    def on_button_pressed(self, event: Button.Pressed) -> None:
        screen = self._screen_for(event.button.id)
        if screen is not None:
            self.app.push_screen(screen)

    def action_back(self) -> None:
        self.app.push_screen(QuitConfirmScreen(), self._quit_if_confirmed)

    def action_show_help(self) -> None:
        show_contextual_help(self.app, type(self).__name__)

    def _quit_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.app.exit()

    def _screen_for(self, item_id: str | None) -> Screen[None] | None:
        if item_id == "wizard":
            return WizardWelcomeScreen(container=self._container)
        if item_id == "capabilities":
            return CapabilitiesScreen(container=self._container)
        if item_id == "profiles":
            return ProfilesScreen(container=self._container)
        if item_id == "server-config":
            return ServerConfigMenuScreen(container=self._container)
        if item_id == "logs":
            return LogsMenuScreen(container=self._container)
        if item_id == "service":
            return ServiceScreen(container=self._container)
        if item_id == "instances":
            return InstancesScreen(container=self._container)
        if item_id == "resource-status":
            return ResourceStatusScreen(container=self._container)
        if item_id == "active-defense":
            return ActiveDefenseMenuScreen(container=self._container)
        if item_id == "audit":
            return AuditScreen(container=self._container)
        if item_id == "backup":
            return BackupScreen(container=self._container)
        return None
