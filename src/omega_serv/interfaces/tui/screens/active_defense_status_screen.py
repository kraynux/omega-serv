"""Ecran Etat (plan_active_defense_omega_serv.md, retour utilisateur
2026-09-12 : "un ecran TUI est bienvenu... piloter tout depuis une
interface") - equivalent TUI de `omega-serv active-defense status`.
Lecture seule, jamais de formulaire de reglages detailles ici (memes
limites que WafModulesScreen : les reglages fins de war_mode/deception
restent a editer a la main dans le JSON ou via CLI, aucun besoin
confirme de formulaire dedie pour l'instant - D-008)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.interfaces.tui.screens._active_defense_collaborators_cache import (
    ActiveDefenseCollaboratorsCacheMixin,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class ActiveDefenseStatusScreen(ActiveDefenseCollaboratorsCacheMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._reset_active_defense_cache()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ACTIVE DEFENSE - ETAT", classes="omega-title")
            yield Static(
                "L'activation de l'option 'active_defense' se fait dans le menu Options "
                "(Configuration detaillee -> Options et verification).",
                classes="omega-hint",
            )
            yield Static("", id="status-body")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        body = self.query_one("#status-body", Static)
        active_defense = self._active_defense_or_none()
        if active_defense is None:
            body.update(self._active_defense_error or "")
            return
        tracked = active_defense.threat_state_repository.list_all()
        lines = [
            f"Active Defense : active (mode={active_defense.config.mode})",
            f"Mode guerre : {'actif' if active_defense.config.war_mode.enabled else 'inactif'}",
            f"Deception : {'active' if active_defense.config.deception.enabled else 'inactive'}",
            f"Sources suivies : {len(tracked)}",
        ]
        body.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
