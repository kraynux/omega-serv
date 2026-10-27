"""Ecran Verifier la configuration (plan interface §10, `config check`) -
structurel (domain/config/validation.py, deja verifie au chargement par
load_config) puis environnement (application/config/validate_config.py,
injecte via container.config_check_runner - voir bootstrap/container.py
pour le pourquoi de cette indirection) puis conflits entre options
(domain/config/rules.py::detect_conflicts - mecanisme existant mais
jusqu'ici jamais cable dans ce sous-ecran, cf. OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §29.4/§30.1 : l'integration ici est l'occasion de le
cabler completement plutot qu'a moitie). Deux severites distinctes :
`"error"` bloque (meme traitement que les erreurs d'environnement),
`"warning"` (ex. chevauchement de prefixe entre deux types de zones)
n'empeche jamais de considerer la configuration valide - seulement
signale."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.rules import detect_conflicts
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
            yield Static(_("VÉRIFIER LA CONFIGURATION"), classes="omega-title")
            yield Static("", id="check-result")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Vérifier"), id="check", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
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
                _("Erreur de configuration :\n") + "\n".join(f"  - {e}" for e in load_result.errors)
            )
            if notify:
                self.app.notify(_("Configuration invalide."), severity="error")
            return
        assert load_result.config is not None

        runner = self._container.config_check_runner
        if runner is None:
            result_widget.update(_("{config_file} : structure valide (vérification d'environnement indisponible).").format(config_file=self._container.config_file))
            if notify:
                self.app.notify(_("Structure valide (vérification d'environnement indisponible)."))
            return

        env_errors = runner(load_result.config, self._container.filesystem, self._container.project_root, False, False)
        if env_errors:
            result_widget.update(_("Erreur d'environnement :\n") + "\n".join(f"  - {e}" for e in env_errors))
            if notify:
                self.app.notify(_("Vérification terminée : {count} erreur(s) d'environnement.").format(count=len(env_errors)), severity="error")
            return

        conflicts = detect_conflicts(load_result.config)
        conflict_errors = [c.message for c in conflicts if c.severity == "error"]
        conflict_warnings = [c.message for c in conflicts if c.severity == "warning"]
        if conflict_errors:
            result_widget.update(_("Erreur de conflit de configuration :\n") + "\n".join(f"  - {e}" for e in conflict_errors))
            if notify:
                self.app.notify(_("Vérification terminée : {count} conflit(s) bloquant(s).").format(count=len(conflict_errors)), severity="error")
            return

        if conflict_warnings:
            result_widget.update(
                _("{config_file} : configuration valide, avec avertissement(s) :\n").format(config_file=self._container.config_file)
                + "\n".join(f"  - {w}" for w in conflict_warnings)
            )
            if notify:
                self.app.notify(
                    _("Vérification terminée : configuration valide, {count} avertissement(s).").format(count=len(conflict_warnings)),
                    severity="warning",
                )
            return

        result_widget.update(_("{config_file} : configuration valide.").format(config_file=self._container.config_file))
        if notify:
            self.app.notify(_("Vérification terminée : configuration valide."))
