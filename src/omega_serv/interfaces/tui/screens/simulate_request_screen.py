# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
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
            yield Static("SIMULER UNE REQUETE", classes="omega-title")
            yield Static("Methode (GET/HEAD/POST...)", classes="omega-subtitle")
            yield Input(value="GET", id="method-input")
            yield Static("Chemin", classes="omega-subtitle")
            yield Input(value="/", id="path-input")
            yield Static("", id="simulate-result", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Simuler", id="simulate", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
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
            result_widget.update("Simulation indisponible dans cet environnement.")
            return

        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            result_widget.update(
                "Erreur de configuration :\n" + "\n".join(f"  - {e}" for e in load_result.errors)
            )
            return
        assert load_result.config is not None

        method = self.query_one("#method-input", Input).value.strip().upper() or "GET"
        path = self.query_one("#path-input", Input).value.strip() or "/"

        report = await runner(method, path, load_result.config, self._container.filesystem, self._container.project_root)

        lines = [
            f"Methode          : {report.method}",
            f"Chemin demande   : {report.raw_path}",
            f"Chemin normalise : {report.normalized_path}",
            f"Methode autorisee: {report.method_allowed}",
            f"Refuse (regles)  : {report.denied_by_access_policy}",
            f"Fichier existe   : {report.file_exists}",
            f"Statut reponse   : {report.response_status}",
        ]
        if report.rejection_reason:
            lines.append(f"Motif de refus   : {report.rejection_reason}")
        lines.append("En-tetes attendus :")
        lines.extend(f"  {name}: {value}" for name, value in report.response_headers.items())
        result_widget.update("\n".join(lines))
