# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase II de l'interface (plan interface §12,
menu 6, hors sauvegarde/restauration - Phase VII) : Verifier la
configuration, Simuler une requete, Audit de securite. Doubles simples
pour les `*_runner` injectes (container.config_check_runner/audit_runner/
simulate_request_runner, voir bootstrap/container.py et __main__.py) -
jamais les vraies fonctions application/ (deja couvertes par leurs
propres tests unitaires, ex. tests/unit/test_run_audit.py)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from textual.widgets import Button, Input

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.security.audit.entities import AuditFinding, AuditResult, Severity
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.audit_screen import AuditScreen
from omega_serv.interfaces.tui.screens.config_check_screen import ConfigCheckScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.resource_status_screen import ResourceStatusScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.simulate_request_screen import SimulateRequestScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiAdvancedTools(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self._checked_with: tuple | None = None

    def tearDown(self):
        self._tmp.cleanup()

    async def _reach_home(self, pilot):
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def _open_config_check(self, pilot) -> None:
        # "Verifier la configuration" ne vit plus au menu principal
        # (retour utilisateur 2026-09-09) - accessible uniquement via
        # Configuration detaillee -> OPTIONS ET VERIFICATION, meme
        # ecran reel qu'avant.
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
        pilot.app.screen.query_one("#config-check", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ConfigCheckScreen)

    async def _open_simulate_request(self, pilot) -> None:
        # "Simuler une requete" ne vit plus au menu principal (retour
        # utilisateur 2026-09-09, remplace par "Etat & Ressources") -
        # accessible uniquement via ce nouvel ecran, meme ecran reel
        # qu'avant.
        pilot.app.screen.query_one("#resource-status", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ResourceStatusScreen)
        pilot.app.screen.query_one("#simulate-request", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, SimulateRequestScreen)

    # --- Verifier la configuration ---

    async def test_config_check_no_config_shows_error(self):
        container = DependencyContainer(project_root=self.root, config_check_runner=lambda *a: [])
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_config_check(pilot)
            self.assertIn("Erreur", str(pilot.app.screen.query_one("#check-result").content))

    async def test_config_check_valid_config_reports_success(self):
        container = DependencyContainer(project_root=self.root, config_check_runner=lambda *a: [])
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_config_check(pilot)
            self.assertIn("valide", str(pilot.app.screen.query_one("#check-result").content))

    async def test_config_check_environment_errors_are_shown(self):
        container = DependencyContainer(
            project_root=self.root, config_check_runner=lambda *a: ["paths.webroot invalide"]
        )
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_config_check(pilot)
            self.assertIn("paths.webroot invalide", str(pilot.app.screen.query_one("#check-result").content))

    # --- Simuler une requete ---

    async def test_simulate_request_calls_runner_with_form_values(self):
        calls = []

        class FakeReport:
            method = "POST"
            raw_path = "/api"
            normalized_path = "/api"
            method_allowed = False
            denied_by_access_policy = False
            file_exists = None
            response_status = 405
            rejection_reason = "methode refusee"
            response_headers: dict = {}  # noqa: RUF012 - simple double de test, jamais sous-classe

        async def fake_runner(method, path, config, filesystem, project_root):
            calls.append((method, path))
            return FakeReport()

        container = DependencyContainer(project_root=self.root, simulate_request_runner=fake_runner)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_simulate_request(pilot)
            method_input = pilot.app.screen.query_one("#method-input", Input)
            method_input.value = "post"
            path_input = pilot.app.screen.query_one("#path-input", Input)
            path_input.value = "/api"
            pilot.app.screen.query_one("#simulate", Button).press()
            await pilot.pause()
            self.assertEqual(calls, [("POST", "/api")])
            result = str(pilot.app.screen.query_one("#simulate-result").content)
            self.assertIn("405", result)
            self.assertIn("methode refusee", result)

    async def test_simulate_request_no_config_shows_error(self):
        async def fake_runner(*a):
            raise AssertionError("ne doit pas etre appele sans configuration")

        container = DependencyContainer(project_root=self.root, simulate_request_runner=fake_runner)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_simulate_request(pilot)
            pilot.app.screen.query_one("#simulate", Button).press()
            await pilot.pause()
            self.assertIn("Erreur", str(pilot.app.screen.query_one("#simulate-result").content))

    # --- Audit de securite ---

    async def test_audit_reports_findings_and_summary(self):
        finding = AuditFinding(
            rule_id="TEST-001", rule_name="Regle de test", severity=Severity.HIGH,
            category="core", message="probleme simule", recommendation="corriger le test",
        )
        result = AuditResult(timestamp=datetime.now(timezone.utc), config_path="omega-serve.json", findings=(finding,))

        def fake_runner(config, config_path, project_root, filesystem, clock, service_name, s1, s2):
            return result

        container = DependencyContainer(project_root=self.root, audit_runner=fake_runner)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            pilot.app.screen.query_one("#audit", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, AuditScreen)
            text = str(pilot.app.screen.query_one("#audit-result").content)
            self.assertIn("TEST-001", text)
            self.assertIn("probleme simule", text)
            self.assertIn("1 high", text)
            self.assertIn("NON SECURISE", text)

    async def test_audit_button_reruns_audit(self):
        calls = {"n": 0}

        def fake_runner(config, config_path, project_root, filesystem, clock, service_name, s1, s2):
            calls["n"] += 1
            return AuditResult(timestamp=datetime.now(timezone.utc), config_path="omega-serve.json", findings=())

        container = DependencyContainer(project_root=self.root, audit_runner=fake_runner)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            pilot.app.screen.query_one("#audit", Button).press()
            await pilot.pause()
            self.assertEqual(calls["n"], 1)
            pilot.app.screen.query_one("#audit", Button).press()
            await pilot.pause()
            self.assertEqual(calls["n"], 2)

    async def test_back_buttons_return_home(self):
        container = DependencyContainer(project_root=self.root)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            pilot.app.screen.query_one("#audit", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, AuditScreen)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_simulate_request_back_button_returns_to_resource_status_screen(self):
        # "Simuler une requete" est reachable uniquement via "Etat &
        # Ressources" desormais (retour utilisateur 2026-09-09) -
        # "Retour" doit donc redescendre vers ce nouvel ecran, pas vers
        # l'accueil.
        container = DependencyContainer(project_root=self.root)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_simulate_request(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ResourceStatusScreen)

    async def test_config_check_back_button_returns_to_server_config_menu(self):
        # "Verifier la configuration" est reachable uniquement via
        # Configuration detaillee desormais (retour utilisateur
        # 2026-09-09) - "Retour" doit donc redescendre vers ce menu 3,
        # pas vers l'accueil.
        container = DependencyContainer(project_root=self.root, config_check_runner=lambda *a: [])
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_config_check(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)


if __name__ == "__main__":
    unittest.main()
