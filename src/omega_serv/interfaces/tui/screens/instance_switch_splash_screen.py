# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran affiche a la place du splash decoratif normal (splash.py)
lorsque ce processus vient d'etre relance par une bascule complete
d'instance (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §6 Niveau 2,
§9 Phase D) - retour utilisateur explicite : jamais repasser par le
splash decoratif standard dans ce cas precis, un rappel court de
"depuis/vers" suffit. Meme convention d'interaction que SplashScreen
(aucune temporisation automatique, une touche ou un clic fait
avancer) - coherence deliberee plutot qu'un nouveau comportement."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Static

if TYPE_CHECKING:
    from pathlib import Path


class InstanceSwitchSplashScreen(Screen[None]):
    def __init__(self, *, source_name: str, current_name: str, current_path: Path) -> None:
        super().__init__()
        self._source_name = source_name
        self._current_name = current_name
        self._current_path = current_path

    def compose(self) -> ComposeResult:
        with Middle(classes="omega-splash-middle"):
            with Center():
                yield Static("BASCULEMENT D'INSTANCE", classes="omega-title")
            with Center():
                yield Static(f"Depuis : {self._source_name}", classes="omega-hint")
            with Center():
                yield Static(f"Vers   : {self._current_name}  ({self._current_path})", classes="omega-hint")
            with Center():
                yield Static("Appuyez sur une touche pour continuer...", classes="omega-splash-prompt")

    def on_key(self, event: events.Key) -> None:
        event.stop()
        self.dismiss()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.dismiss()
