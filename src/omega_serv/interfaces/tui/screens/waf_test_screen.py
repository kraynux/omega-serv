"""Sous-ecran Tester une regle WAF - extrait de l'ancien WafMenuScreen
unique (retour utilisateur 2026-09-13, restructuration Etat/Modules/
Tester/Custom). `container.waf_test_runner` injecte depuis __main__.py
car le cas d'usage touche infrastructure/ transitivement (meme raison
que les autres usines de ce module)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


class WafTestScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("WAF - TESTER UNE RÈGLE"), classes="omega-title")
            yield Input(value="GET", id="test-method-input")
            yield Input(value="/", id="test-path-input")
            yield Input(placeholder="query", id="test-query-input")
            yield Input(placeholder="body", id="test-body-input")
            yield Input(value="127.0.0.1", id="test-remote-ip-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Tester"), id="test", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
            yield Static("", id="test-result", classes="omega-hint")
        yield Footer()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "test":
            await self._run_test()

    async def _run_test(self) -> None:
        result_widget = self.query_one("#test-result", Static)
        runner = self._container.waf_test_runner
        if runner is None:
            result_widget.update(_("Test indisponible dans cet environnement."))
            return
        config = self._config()
        if config is None:
            result_widget.update(_("Erreur de configuration."))
            return
        report = await runner(
            self.query_one("#test-method-input", Input).value.strip() or "GET",
            self.query_one("#test-path-input", Input).value.strip() or "/",
            self.query_one("#test-query-input", Input).value.strip(),
            self.query_one("#test-body-input", Input).value.strip(),
            self.query_one("#test-remote-ip-input", Input).value.strip() or "127.0.0.1",
            config,
            self._container.filesystem,
            self._container.project_root,
            self._container.clock,
        )
        if report is None:
            result_widget.update(_("WAF indisponible (option 'waf' absente de la configuration)."))
            return
        decision = report.decision
        lines = [
            _("Décision : {value}").format(value=decision.action.upper()),
            _("Statut : {value}").format(value=decision.status_code if decision.status_code is not None else '-'),
            _("Score : {score}").format(score=decision.score),
            _("Règles : {value}").format(value=', '.join(f.rule_id for f in decision.findings) or '-'),
            _("Politique de zone : {zone_id}").format(zone_id=report.zone_id),
            _("Mode : {mode}").format(mode=report.mode),
        ]
        if decision.blocked_reason:
            lines.append(_("Motif : {blocked_reason}").format(blocked_reason=decision.blocked_reason))
        if report.magnet_error:
            lines.append(_("ATTENTION script magnet en erreur : {magnet_error}").format(magnet_error=report.magnet_error))
        if report.magnet_unsupported_members:
            lines.append(
                _("ATTENTION lighty.") + _("{{{value}}} non supporte par ce pont").format(value=', '.join(sorted(report.magnet_unsupported_members)))
            )
        result_widget.update("\n".join(lines))
