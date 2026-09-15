# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase VIII de l'interface (plan interface §12,
§11) : assistant premier lancement, bout en bout et etape par etape.
`certificate_tool_factory` utilise le vrai `OpensslCertificateTool`
(meme discipline que test_tui_tls.py) - aucun mock d'un mecanisme
touchant reellement le systeme de fichiers/subprocess."""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.css.query import NoMatches
from textual.widgets import Button, Checkbox, DataTable, Input

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.service_screen import ServiceScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.screens.wizard_base_config_screen import WizardBaseConfigScreen
from omega_serv.interfaces.tui.screens.wizard_capabilities_screen import WizardCapabilitiesScreen
from omega_serv.interfaces.tui.screens.wizard_check_screen import WizardCheckScreen
from omega_serv.interfaces.tui.screens.wizard_profile_screen import WizardProfileScreen
from omega_serv.interfaces.tui.screens.wizard_service_screen import WizardServiceScreen
from omega_serv.interfaces.tui.screens.wizard_summary_screen import WizardSummaryScreen
from omega_serv.interfaces.tui.screens.wizard_tls_screen import WizardTlsScreen
from omega_serv.interfaces.tui.screens.wizard_welcome_screen import WizardWelcomeScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _build_certificate_tool():
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
    from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

    return OpensslCertificateTool(SubprocessRunner())


def _run_config_check(config, filesystem, project_root, self_signed_public_bind_confirmed, auth_without_tls_confirmed):
    from omega_serv.application.config.validate_config import validate_config_environment

    return validate_config_environment(
        config, filesystem, project_root,
        self_signed_public_bind_confirmed=self_signed_public_bind_confirmed,
        auth_without_tls_confirmed=auth_without_tls_confirmed,
    )


class TestTuiWizard(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, **kwargs) -> DependencyContainer:
        kwargs.setdefault("certificate_tool_factory", _build_certificate_tool)
        kwargs.setdefault("config_check_runner", _run_config_check)
        return DependencyContainer(project_root=self.root, **kwargs)

    async def _wait_for_generate_to_finish(self, pilot) -> None:
        # Retour utilisateur (audit "gel d'ecran") : la generation TLS
        # de l'assistant tourne desormais dans un thread de travail
        # (run_worker(thread=True)) pour ne plus geler l'interface -
        # meme patron de sondage que test_tui_tls.py.
        for _ in range(40):
            await pilot.pause()
            if not pilot.app.screen.query_one("#generate", Button).disabled:
                return
            await asyncio.sleep(0.05)
        self.fail("la generation ne s'est jamais terminee")

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_wizard(self, pilot) -> None:
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#wizard", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, WizardWelcomeScreen)

    async def _select_profile(self, pilot, name: str) -> None:
        table = pilot.app.screen.query_one("#profiles-table", DataTable)
        names = [table.get_row_at(i)[0] for i in range(table.row_count)]
        table.move_cursor(row=names.index(name))
        await pilot.pause()
        table.action_select_cursor()
        await pilot.pause()

    async def test_welcome_back_returns_home(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_full_flow_development_profile_skips_tls_and_writes_config(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)

            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardCapabilitiesScreen)

            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardProfileScreen)
            await self._select_profile(pilot, "development")
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardBaseConfigScreen)

            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardTlsScreen)

            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardCheckScreen)
            self.assertFalse(pilot.app.screen.query_one("#next", Button).disabled)

            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardSummaryScreen)
            diff_text = str(pilot.app.screen.query_one("#summary-diff").content)
            self.assertIn("development", diff_text)

            pilot.app.screen.query_one("#write", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardServiceScreen)
        self.assertTrue(container.config_file.exists())
        self.assertIn('"profile": "development"', container.config_file.read_text())

    async def test_tls_step_skipped_message_for_development_profile(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            await self._select_profile(pilot, "development")
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardTlsScreen)
            with self.assertRaises(NoMatches):
                pilot.app.screen.query_one("#generate", Button)

    async def test_profile_step_next_disabled_until_selection(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardProfileScreen)
            self.assertTrue(pilot.app.screen.query_one("#next", Button).disabled)

    async def test_base_config_step_rejects_invalid_port(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            await self._select_profile(pilot, "standard")
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardBaseConfigScreen)

            pilot.app.screen.query_one("#port-input", Input).value = "not-a-number"
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardBaseConfigScreen)
            self.assertIn("invalide", str(pilot.app.screen.query_one("#form-error").content))

    async def test_full_flow_standard_profile_with_real_self_signed_tls(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            await self._select_profile(pilot, "standard")
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardTlsScreen)

            pilot.app.screen.query_one("#cn-input", Input).value = "test.local"
            pilot.app.screen.query_one("#san-dns-input", Input).value = "test.local"
            pilot.app.screen.query_one("#generate", Button).press()
            await self._wait_for_generate_to_finish(pilot)
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardCheckScreen)
            self.assertFalse(pilot.app.screen.query_one("#next", Button).disabled)
        cert_path = self.root / "secure" / "certificates" / "server" / "server.pem"
        self.assertTrue(cert_path.exists())

    async def test_check_step_blocks_self_signed_public_bind_until_confirmed(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            await self._select_profile(pilot, "standard")
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()

            pilot.app.screen.query_one("#bind-input", Input).value = "0.0.0.0"
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardTlsScreen)
            pilot.app.screen.query_one("#cn-input", Input).value = "test.local"
            pilot.app.screen.query_one("#san-dns-input", Input).value = "test.local"
            pilot.app.screen.query_one("#generate", Button).press()
            await self._wait_for_generate_to_finish(pilot)

            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardCheckScreen)
            self.assertTrue(pilot.app.screen.query_one("#next", Button).disabled)
            self.assertIn("auto-signe", str(pilot.app.screen.query_one("#check-result").content))

            pilot.app.screen.query_one("#confirm-self-signed", Checkbox).value = True
            pilot.app.screen.query_one("#check", Button).press()
            await pilot.pause()
            self.assertFalse(pilot.app.screen.query_one("#next", Button).disabled)

    async def test_back_navigation_returns_to_previous_step(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardCapabilitiesScreen)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardWelcomeScreen)

    async def test_service_step_install_pushes_service_screen(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            await self._select_profile(pilot, "development")
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#write", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardServiceScreen)

            pilot.app.screen.query_one("#install", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServiceScreen)

    async def _reach_service_step(self, pilot) -> None:
        await self._start(pilot)
        await self._open_wizard(pilot)
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()
        await self._select_profile(pilot, "development")
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#write", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, WizardServiceScreen)

    async def test_service_step_launch_now_runs_real_server_then_returns_home(self):
        # Retour utilisateur 2026-09-09 : le bouton "Lancer maintenant"
        # doit reellement attendre `container.serve_foreground_runner`
        # (une coroutine) sur la boucle DEJA active de Textual, jamais
        # l'envelopper dans un `asyncio.run()` imbrique (RuntimeError
        # verifie empiriquement avant ce correctif) - ce double appele
        # confirme a la fois que le callable recoit bien le chemin de
        # config + le conteneur, et que l'ecran revient a l'accueil une
        # fois la coroutine terminee (serveur "arrete").
        calls = []

        async def fake_serve_foreground(config_path, container) -> int:
            calls.append((config_path, container))
            return 0

        container = self._container(serve_foreground_runner=fake_serve_foreground)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._reach_service_step(pilot)
            pilot.app.screen.query_one("#launch-now", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], (container.config_file, container))

    async def test_service_step_launch_now_unavailable_shows_error_without_crashing(self):
        container = self._container()  # aucun serve_foreground_runner injecte
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._reach_service_step(pilot)
            pilot.app.screen.query_one("#launch-now", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardServiceScreen)

    async def test_service_step_finish_returns_home(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 55)) as pilot:
            await self._start(pilot)
            await self._open_wizard(pilot)
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            await self._select_profile(pilot, "development")
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#next", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#write", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WizardServiceScreen)

            pilot.app.screen.query_one("#finish", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)


if __name__ == "__main__":
    unittest.main()
