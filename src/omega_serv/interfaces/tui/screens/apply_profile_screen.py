"""Ecran d'application d'un profil (plan interface §6, `profile apply`) -
le diff (spec §9.2) s'affiche TOUJOURS avant toute confirmation, jamais
une case a cocher qui le masque (meme regle que la CLI). Reutilise
application/config/apply_profile.py::plan_profile_application, aucune
nouvelle logique metier ici."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.apply_profile import ApplyProfileResult, plan_profile_application
from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.restart_prompt import (
    notify_reload_required,
    notify_restart_required,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


class ApplyProfileScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, profile_name: str) -> None:
        super().__init__()
        self._container = container
        self._profile_name = profile_name
        self._plan: ApplyProfileResult | None = None
        self._previous_config: OmegaServConfig | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(f"APPLIQUER LE PROFIL '{self._profile_name.upper()}'", classes="omega-title")
            yield Static("", id="plan-text")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Appliquer", id="apply", variant="primary", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            self.query_one("#plan-text", Static).update(
                "Configuration introuvable ou invalide : " + "; ".join(load_result.errors) +
                "\n\nCreez d'abord une configuration (`omega-serv config init` en CLI pour l'instant)."
            )
            return
        assert load_result.config is not None

        try:
            profile = self._container.profiles.load_profile(self._profile_name)
        except (ProfileNotFoundError, ProfileLoadError) as exc:
            self.query_one("#plan-text", Static).update(f"Erreur : {exc}")
            return

        self._previous_config = load_result.config
        self._plan = plan_profile_application(load_result.config, profile)
        self.query_one("#plan-text", Static).update(self._render_plan())
        self.query_one("#apply", Button).disabled = False

    def _render_plan(self) -> str:
        assert self._plan is not None
        lines = []
        if not self._plan.changes:
            lines.append("Aucune modification.")
        else:
            lines.append("Modifications :")
            lines.extend(str(change) for change in self._plan.changes)
        if self._plan.conflicts:
            lines.append("")
            lines.append("Conflits detectes :")
            lines.extend(f"  [{c.severity.upper()}] {c.message}" for c in self._plan.conflicts)
        if self._plan.validation_errors:
            lines.append("")
            lines.append("Erreurs de validation :")
            lines.extend(f"  - {e}" for e in self._plan.validation_errors)
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "apply" and self._plan is not None:
            if self._plan.has_blocking_issues:
                self.app.push_screen(
                    ConfirmScreen(
                        title="PROBLEMES BLOQUANTS DETECTES",
                        message="Des conflits ou erreurs de validation existent (voir ci-dessus). "
                        "Forcer l'application quand meme ?",
                    ),
                    self._apply_if_confirmed,
                )
            else:
                self._apply_if_confirmed(True)

    def _apply_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._plan is None:
            return
        self._container.configuration.save(self._container.config_file, self._plan.new_config)
        message = f"Profil '{self._profile_name}' applique dans {self._container.config_file}."
        new_server = self._plan.new_config.server
        new_tls = self._plan.new_config.tls
        needs_restart = self._previous_config is not None and (
            new_server.bind != self._previous_config.server.bind
            or new_server.port != self._previous_config.server.port
            or new_server.listen_backlog != self._previous_config.server.listen_backlog
            or new_tls != self._previous_config.tls
        )
        if needs_restart:
            notify_restart_required(
                self, self._container,
                f"{message} Necessite un REDEMARRAGE COMPLET pour prendre effet (bind/port/"
                "listen_backlog/TLS ont change).",
            )
        else:
            notify_reload_required(self, self._container, message)
            self.dismiss()
