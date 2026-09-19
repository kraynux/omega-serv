"""Ecran Audit de securite (plan interface §10, `audit security`) -
meme jeu de regles que le CLI (application/security/run_audit.py),
injecte via container.audit_runner (bootstrap/container.py) : le cas
d'usage a besoin d'un CertificateToolPort reel (infrastructure/tls/,
via subprocess), que interfaces.tui/ ne peut jamais construire elle-meme
(plan interface §1/§3.6)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.security.audit.entities import Severity
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.security.audit.entities import AuditResult
    from omega_serv.ports.clock_port import ClockPort
    from omega_serv.ports.filesystem_port import FilesystemPort

    AuditRunner = Callable[[OmegaServConfig, Path, Path, FilesystemPort, ClockPort, str, bool, bool], AuditResult]

_SEVERITY_LABELS = {
    Severity.CRITICAL: "CRITICAL", Severity.HIGH: "HIGH", Severity.MEDIUM: "MEDIUM",
    Severity.LOW: "LOW", Severity.INFO: "INFO",
}

_DEFAULT_SERVICE_NAME = "omega-serv"


class AuditScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("AUDIT DE SECURITE", classes="omega-title")
            yield Static("", id="audit-result")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Auditer", id="audit", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._run_audit(notify=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "audit":
            self._run_audit(notify=True)

    def _run_audit(self, *, notify: bool) -> None:
        result_widget = self.query_one("#audit-result", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            result_widget.update(
                "Erreur de configuration :\n" + "\n".join(f"  - {e}" for e in load_result.errors)
            )
            if notify:
                self.app.notify("Audit impossible : configuration invalide.", severity="error")
            return
        assert load_result.config is not None

        runner = self._container.audit_runner
        if runner is None:
            result_widget.update("Audit indisponible dans cet environnement.")
            if notify:
                self.app.notify("Audit indisponible dans cet environnement.", severity="error")
            return

        result_widget.update("Audit en cours...")
        self.query_one("#audit", Button).disabled = True
        config = load_result.config
        self.run_worker(lambda: self._run_audit_in_thread(runner, config, notify), thread=True, exclusive=True)

    def _run_audit_in_thread(self, runner: AuditRunner, config: OmegaServConfig, notify: bool) -> None:
        audit = runner(
            config, self._container.config_file, self._container.project_root,
            self._container.filesystem, self._container.clock, _DEFAULT_SERVICE_NAME, False, False,
        )
        self.app.call_from_thread(self._finish_audit, audit, notify)

    def _finish_audit(self, audit: AuditResult, notify: bool) -> None:
        self.query_one("#audit", Button).disabled = False
        result_widget = self.query_one("#audit-result", Static)

        lines: list[str] = []
        if not audit.findings:
            lines.append("Aucun probleme detecte.")
        else:
            for finding in audit.findings:
                label = _SEVERITY_LABELS[finding.severity]
                lines.append(f"[{label}] {finding.rule_id} {finding.rule_name}")
                lines.append(f"    {finding.message}")
                lines.append(f"    -> {finding.recommendation}")
        summary = audit.summary
        lines.append("")
        lines.append(
            f"Resume : {summary['critical']} critical, {summary['high']} high, "
            f"{summary['medium']} medium, {summary['low']} low, {summary['info']} info"
        )
        lines.append("Etat : securise" if audit.is_secure else "Etat : NON SECURISE")
        result_widget.update("\n".join(lines))
        if notify:
            self.app.notify(
                "Audit termine : aucun probleme detecte." if audit.is_secure
                else f"Audit termine : {summary['critical']} critical, {summary['high']} high.",
                severity="information" if audit.is_secure else "warning",
            )
