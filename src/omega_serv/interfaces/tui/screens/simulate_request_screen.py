"""Ecran Simuler une requete (plan interface §10, `simulate-request`) -
rejoue le routage reel (application/server/route_request.py, via
application/server/simulate_request.py) sans requete reseau. Injecte via
container.simulate_request_runner (bootstrap/container.py) - le cas
d'usage lui-meme importe infrastructure/filesystem/safe_path_resolver.py
pour construire son resolveur de chemin, ce que interfaces.tui/ ne peut
jamais faire directement (plan interface §1/§3.6)."""
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


class SimulateRequestScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static(_("SIMULER UNE REQUÊTE"), classes="omega-title")
            yield Static(_("Méthode (GET/HEAD/POST...)"), classes="omega-subtitle")
            yield Input(value="GET", id="method-input")
            yield Static(_("Chemin"), classes="omega-subtitle")
            yield Input(value="/", id="path-input")
            yield Static("", id="simulate-result", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Simuler"), id="simulate", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "simulate":
            await self._run_simulation()

    async def _run_simulation(self) -> None:
        result_widget = self.query_one("#simulate-result", Static)
        runner = self._container.simulate_request_runner
        if runner is None:
            result_widget.update(_("Simulation indisponible dans cet environnement."))
            return

        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            result_widget.update(
                _("Erreur de configuration :\n") + "\n".join(f"  - {e}" for e in load_result.errors)
            )
            return
        assert load_result.config is not None

        method = self.query_one("#method-input", Input).value.strip().upper() or "GET"
        path = self.query_one("#path-input", Input).value.strip() or "/"

        report = await runner(method, path, load_result.config, self._container.filesystem, self._container.project_root)

        lines = [
            _("Méthode          : {method}").format(method=report.method),
            _("Chemin demandé   : {raw_path}").format(raw_path=report.raw_path),
            _("Chemin normalisé : {normalized_path}").format(normalized_path=report.normalized_path),
            _("Méthode autorisée: {method_allowed}").format(method_allowed=report.method_allowed),
            _("Refusé (règles)  : {denied_by_access_policy}").format(denied_by_access_policy=report.denied_by_access_policy),
            _("Fichier existe   : {file_exists}").format(file_exists=report.file_exists),
            _("Statut réponse   : {response_status}").format(response_status=report.response_status),
        ]
        if report.rejection_reason:
            lines.append(_("Motif de refus   : {rejection_reason}").format(rejection_reason=report.rejection_reason))
        lines.append(_("En-têtes attendus :"))
        lines.extend(f"  {name}: {value}" for name, value in report.response_headers.items())
        result_widget.update("\n".join(lines))
