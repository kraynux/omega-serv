"""Ecran Verifier la configuration (plan interface §10, `config check`) -
structurel (domain/config/validation.py, deja verifie au chargement par
load_config) puis environnement (application/config/validate_config.py,
injecte via container.config_check_runner - voir bootstrap/container.py
pour le pourquoi de cette indirection)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class ConfigCheckScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("VERIFIER LA CONFIGURATION", classes="omega-title")
            yield Static("", id="check-result")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Verifier", id="check", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._run_check(notify=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "check":
            self._run_check(notify=True)

    def _run_check(self, *, notify: bool) -> None:
        result_widget = self.query_one("#check-result", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            result_widget.update(
                "Erreur de configuration :\n" + "\n".join(f"  - {e}" for e in load_result.errors)
            )
            if notify:
                self.app.notify("Configuration invalide.", severity="error")
            return
        assert load_result.config is not None

        runner = self._container.config_check_runner
        if runner is None:
            result_widget.update(f"{self._container.config_file} : structure valide (verification d'environnement indisponible).")
            if notify:
                self.app.notify("Structure valide (verification d'environnement indisponible).")
            return

        env_errors = runner(load_result.config, self._container.filesystem, self._container.project_root, False, False)
        if env_errors:
            result_widget.update("Erreur d'environnement :\n" + "\n".join(f"  - {e}" for e in env_errors))
            if notify:
                self.app.notify(f"Verification terminee : {len(env_errors)} erreur(s) d'environnement.", severity="error")
            return
        result_widget.update(f"{self._container.config_file} : configuration valide.")
        if notify:
            self.app.notify("Verification terminee : configuration valide.")
