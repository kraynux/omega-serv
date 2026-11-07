"""Ecran de demarrage : composition ASCII, se ferme sur une touche ou un clic.
Porte verbatim depuis omega-check (plan interface §0/§3.1)."""
from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.widgets.splash_hero import SplashHero


class SplashScreen(Screen[None]):
    """Premier ecran affiche par app.py. Aucun appel a application/ ici :
    contenu statique. Pas de temporisation automatique : seule une action
    explicite (touche ou clic) fait passer a la suite. `version` : celle de pyproject.toml (app.py)."""

    def __init__(self, *, version: str) -> None:
        super().__init__()
        self._version = version

    def compose(self) -> ComposeResult:
        with Middle(classes="omega-splash-middle"):
            with Center():
                yield SplashHero(self._version)
            with Center():
                yield Static(_("Cliquez ou appuyez sur une touche pour continuer..."), classes="omega-splash-prompt")

    def on_key(self, event: events.Key) -> None:
        event.stop()
        self.dismiss()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.dismiss()
