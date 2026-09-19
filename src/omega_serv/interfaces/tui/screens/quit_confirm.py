"""Ecran de confirmation avant fermeture de l'application.
Porte verbatim depuis omega-check (plan interface §0/§3.1)."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static


class QuitConfirmScreen(Screen[bool]):
    """Demande confirmation avant de fermer l'application. Resultat bool
    transmis au callback de push_screen() ; n'herite pas de OmegaScreen
    (`echap` ici doit annuler la sortie, pas dismiss(None))."""

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-confirm-box"):
            yield Static("QUITTER OMEGA-SERV ?", classes="omega-confirm-title")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Oui, quitter", id="confirm", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button("Non, continuer", id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")
