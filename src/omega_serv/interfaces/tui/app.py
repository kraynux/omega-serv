# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Point d'entree Textual de l'application, cable par le composition
root (bootstrap/container.py). Adapte du patron app.py d'omega-check
(plan interface §0/§3.1 : patron de coquille applicative de reference)."""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, ClassVar, cast

from omega_lib.terminal.models import RenderProfile
from omega_lib.theme.policies import TUI_THEMES
from textual.app import App, SystemCommand
from textual.binding import Binding, BindingType

from omega_serv.application.terminal.detect_terminal import detect_terminal
from omega_serv.application.terminal.exceptions import UnknownThemeError
from omega_serv.application.terminal.select_theme import select_theme
from omega_serv.interfaces.tui.controllers.startup_controller import (
    StartupState,
    resolve_startup_state,
)
from omega_serv.interfaces.tui.pending_instance_switch import PendingInstanceSwitch
from omega_serv.interfaces.tui.rendering.stylesheet_loader import load_paths_for
from omega_serv.interfaces.tui.rendering.textual_theme_builder import build_all_textual_themes
from omega_serv.interfaces.tui.screens.guide_menu_screen import GuideMenuScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.instance_switch_splash_screen import (
    InstanceSwitchSplashScreen,
)
from omega_serv.interfaces.tui.screens.quit_confirm import QuitConfirmScreen
from omega_serv.interfaces.tui.screens.settings_screen import SettingsScreen
from omega_serv.interfaces.tui.screens.splash import SplashScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

if TYPE_CHECKING:
    from textual.screen import Screen

    from omega_serv.bootstrap.container import DependencyContainer

TITLE = "\U0001f512 OMEGA-SERV"
"""Icone cadenas incluse DANS la chaine de titre (HeaderIcon/HeaderTitle
sont deux widgets Textual distincts, les fondre dans une seule chaine
les fait apparaitre comme une unite - meme raisonnement que le reste de
la suite)."""

_SWITCHED_FROM_ENV_VAR = "OMEGA_SERV_SWITCHED_FROM"
"""Seul canal qui survit a un os.execv() (OMEGA-SERV_PLAN-DETAILLE_
MULTI_INSTANCE.md §9 Phase D) - remplacer le process efface toute la
memoire Python, seules les variables d'environnement traversent
l'appel. Consommee (retiree) des la lecture, jamais laissee trainer
pour le reste de la vie du process."""


class OmegaServApp(App[None]):
    """Application TUI d'omega-serv : resout theme/profil de rendu au
    demarrage, puis enchaine splash -> (avertissement terminal) -> accueil.

    Aucun privilege particulier requis pour lancer cette interface -
    contrairement a `serve` (refuse root), et contrairement a la gestion
    du service systeme qui elevera ponctuellement ses propres privileges
    au moment de l'action concernee (plan interface §3.6), jamais au
    lancement de l'application entiere."""

    TITLE = TITLE
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quitter", show=True),
        Binding("ctrl+q", "quit", "Quitter", show=False),
        Binding("t", "cycle_theme", "Theme suivant", show=True),
        Binding("r", "refresh_terminal", "Rafraichir", show=True),
        Binding("a", "help", "Aide", show=True),
        Binding("o", "open_settings", "Options", show=True),
    ]

    def __init__(self, container: DependencyContainer) -> None:
        self._container = container
        self._startup_state = resolve_startup_state(
            terminal_detector=container.terminal_detector,
            settings_store=container.settings_store,
        )
        css_path = cast(
            "list[str | PurePath]", load_paths_for(self._startup_state.theme.render_profile)
        )
        super().__init__(css_path=css_path)
        for theme in build_all_textual_themes():
            self.register_theme(theme)
        self.theme = self._startup_state.theme.theme_name
        # Lu par omega_serv/__main__.py::main() APRES que run() soit
        # revenu - jamais consomme depuis l'interieur de l'app elle-meme
        # (§9 Phase D : os.execv() n'a lieu qu'une fois Textual arrete).
        self.pending_switch: PendingInstanceSwitch | None = None

    def on_mount(self) -> None:
        switched_from = os.environ.pop(_SWITCHED_FROM_ENV_VAR, None)
        if switched_from is not None:
            self.push_screen(
                InstanceSwitchSplashScreen(
                    source_name=switched_from,
                    current_name=self._current_instance_display_name(),
                    current_path=self._container.project_root,
                ),
                self._after_splash,
            )
        else:
            self.push_screen(SplashScreen(), self._after_splash)

    def _current_instance_display_name(self) -> str:
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        for entry in self._container.instance_registry.load():
            if entry.path == current_path:
                return entry.name
        return self._container.project_root.name

    def _after_splash(self, _result: None) -> None:
        terminal = self._startup_state.terminal
        too_small = terminal.signals.columns < 80 or terminal.signals.rows < 24
        if terminal.render_profile == RenderProfile.MONO or too_small:
            message = (
                f"Terminal detecte : {terminal.signals.family} "
                f"({terminal.signals.columns}x{terminal.signals.rows}). "
                f"Rendu applique : {terminal.render_profile.value}."
            )
            self.push_screen(TerminalWarningScreen(message=message), self._show_home)
        else:
            self._show_home(None)

    def _show_home(self, _result: None) -> None:
        self.push_screen(HomeScreen(container=self._container))

    def watch_theme(self, _theme_name: str) -> None:
        self.sub_title = self._build_sub_title()

    def _build_sub_title(self) -> str:
        terminal = self._startup_state.terminal
        base = f"{self.theme} | {terminal.signals.columns}x{terminal.signals.rows}"
        # Retour utilisateur (plan multi-instance §7) : rappel visuel
        # invisible pour le cas tres majoritaire (0/1 instance connue) -
        # zero changement percu, jamais de bruit pour rien.
        instance_count = len(self._container.instance_registry.load())
        if instance_count <= 1:
            return base
        return f"{base} | Instance : {self._current_instance_display_name()}"

    async def action_quit(self) -> None:
        """Surcharge : demande confirmation avant de fermer."""
        self.push_screen(QuitConfirmScreen(), self._quit_if_confirmed)

    def _quit_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.exit()

    def action_cycle_theme(self) -> None:
        """Touche `t` : bascule vers le theme SUIVANT du catalogue, sans
        confirmation."""
        names = list(TUI_THEMES.keys())
        current_index = names.index(self.theme) if self.theme in names else 0
        next_name = names[(current_index + 1) % len(names)]
        try:
            select_theme(settings_store=self._container.settings_store, theme_name=next_name)
        except UnknownThemeError as exc:
            self.notify(str(exc), severity="error")
            return
        except OSError as exc:
            # Retour utilisateur (GROS BUG omega-fire : "t" fermait
            # l'application) - meme correctif applique ici par coherence
            # (audit de la suite) : une simple erreur de persistance
            # (permissions, disque plein, systeme de fichiers en lecture
            # seule) faisait planter cette action sans aucun rattrapage.
            # Le theme change quand meme visuellement (self.theme =
            # next_name plus bas) : seule la PERSISTANCE du choix
            # echoue, pas la fonctionnalite immediate.
            self.notify(f"Theme applique mais non enregistre : {exc}", severity="warning")
        self.theme = next_name

    def action_refresh_terminal(self) -> None:
        """Touche `r` : redetecte taille/famille du terminal et met a
        jour le sous-titre du Header."""
        terminal = detect_terminal(terminal_detector=self._container.terminal_detector)
        self._startup_state = StartupState(terminal=terminal, theme=self._startup_state.theme)
        self.sub_title = self._build_sub_title()
        self.notify(
            f"{terminal.signals.family} ({terminal.signals.columns}x{terminal.signals.rows})",
            title="Terminal rafraichi",
        )

    def action_help(self) -> None:
        # Guide d'aide (plan guide d'aide §3.6) : `a` ouvre desormais le
        # menu navigable complet, plutot que la seule reference statique
        # d'antan (HelpScreen reste le repli quand une fiche precise
        # n'existe pas encore, voir _base.py::action_show_help).
        self.push_screen(GuideMenuScreen(container=self._container))

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(container=self._container))

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        """Remplace la liste par defaut de Textual plutot que d'appeler
        `super()` (meme raisonnement que le reste de la suite)."""
        yield SystemCommand("Theme", "Changer le theme actif", self.action_change_theme)
        yield SystemCommand(
            "Quitter", "Quitter l'application (avec confirmation)", self.action_quit
        )
        yield SystemCommand(
            "Capture d'ecran",
            "Enregistrer une capture SVG de l'ecran courant",
            self._deliver_screenshot_to_configured_dir,
        )
        yield SystemCommand(
            "Options", "Theme, profil de rendu, chemins d'export/captures", self.action_open_settings
        )

    def _deliver_screenshot_to_configured_dir(self) -> None:
        configured = self._container.settings_store.get(
            "screenshots_dir_override", str(self._container.default_screenshots_dir)
        )
        directory = Path(configured or self._container.default_screenshots_dir)
        directory.mkdir(parents=True, exist_ok=True)
        self.deliver_screenshot(path=str(directory))

    def _handle_exception(self, error: Exception) -> None:
        """Filet de securite unique cote TUI : toute exception technique
        non prevue est journalisee puis affichee comme notification,
        sans jamais fermer l'application."""
        logging.getLogger("omega_serv").error("Exception non prevue", exc_info=error)
        self.notify(
            str(error) or type(error).__name__,
            title="Erreur inattendue",
            severity="error",
            timeout=10,
        )
