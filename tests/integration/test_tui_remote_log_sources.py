"""Tests d'integration pour l'ecran Sources distantes (SSH)
(OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md, 2026-10-15) - double
simple pour `container.remote_log_fetch_runner_factory` (jamais un vrai
`scp` invoque par une suite automatisee, meme discipline que
`test_tui_lets_encrypt.py`/`_FakeCertbotRunner`)."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, DataTable, Input

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.logs.library import list_library
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.log_library_screen import LogLibraryScreen
from omega_serv.interfaces.tui.screens.logs_menu_screen import LogsMenuScreen
from omega_serv.interfaces.tui.screens.remote_log_sources_screen import RemoteLogSourcesScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.ports.process_runner_port import ProcessResult

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _FakeScpRunner:
    """`succeeds=True` ecrit un vrai fichier a la destination (dernier
    element de l'argv) pour simuler fidelement ce qu'un vrai `scp`
    ferait ; `succeeds=False` n'ecrit rien (simule un hote injoignable
    ou un echec d'authentification)."""

    def __init__(self, *, succeeds: bool = True, stderr: str = "Connection refused") -> None:
        self._succeeds = succeeds
        self._stderr = stderr
        self.calls: list[list[str]] = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append(args)
        if self._succeeds:
            local_dest = Path(args[-1])
            local_dest.parent.mkdir(parents=True, exist_ok=True)
            local_dest.write_text("ligne distante 1\n")
            return ProcessResult(returncode=0, stdout="", stderr="")
        return ProcessResult(returncode=1, stdout="", stderr=self._stderr)

    def run_interactive(self, args):
        raise NotImplementedError


class TestTuiRemoteLogSources(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        import shutil
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        (self.root / "var" / "log").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, **kwargs) -> DependencyContainer:
        return DependencyContainer(project_root=self.root, **kwargs)

    def _generate_config(self, container: DependencyContainer) -> None:
        generate_default_config(container.configuration, container.filesystem, container.config_file)

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_remote_sources(self, pilot) -> None:
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#logs", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogsMenuScreen)
        pilot.app.screen.query_one("#library", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogLibraryScreen)
        pilot.app.screen.query_one("#remote-sources", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, RemoteLogSourcesScreen)

    def _fill_source_form(self, screen, *, label="backend1", host="192.168.1.10", remote_path="/var/log/access.log"):
        screen.query_one("#label-input", Input).value = label
        screen.query_one("#host-input", Input).value = host
        screen.query_one("#remote-path-input", Input).value = remote_path

    async def test_save_adds_source_to_table(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            self._fill_source_form(pilot.app.screen)
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#sources-table", DataTable)
            self.assertEqual(table.row_count, 1)

    async def test_save_rejects_blank_required_field(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            pilot.app.screen.query_one("#host-input", Input).value = "192.168.1.10"
            pilot.app.screen.query_one("#remote-path-input", Input).value = "/var/log/access.log"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("Label requis", str(pilot.app.screen.query_one("#sources-error").content))
            table = pilot.app.screen.query_one("#sources-table", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_save_rejects_invalid_port(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            self._fill_source_form(pilot.app.screen)
            pilot.app.screen.query_one("#port-input", Input).value = "abc"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("Port invalide", str(pilot.app.screen.query_one("#sources-error").content))

    async def test_fetch_success_adds_to_library(self):
        fake_runner = _FakeScpRunner(succeeds=True)
        container = self._container(remote_log_fetch_runner_factory=lambda: fake_runner)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            self._fill_source_form(pilot.app.screen)
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#sources-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#fetch", Button).press()
            await pilot.pause()
            await asyncio.sleep(0.3)
            await pilot.pause()
            self.assertEqual(len(fake_runner.calls), 1)

        entries = list_library(container.build_log_library_repository())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].access, "ssh")
        self.assertEqual(entries[0].service_id, "backend1")
        self.assertTrue(entries[0].exists)

    async def test_fetch_failure_shows_error_and_does_not_add_to_library(self):
        fake_runner = _FakeScpRunner(succeeds=False, stderr="Connection refused")
        container = self._container(remote_log_fetch_runner_factory=lambda: fake_runner)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            self._fill_source_form(pilot.app.screen)
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#sources-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#fetch", Button).press()
            await pilot.pause()
            await asyncio.sleep(0.3)
            await pilot.pause()
            self.assertIn("Connection refused", str(pilot.app.screen.query_one("#sources-error").content))

        entries = list_library(container.build_log_library_repository())
        self.assertEqual(entries, [])

    async def test_fetch_unavailable_without_injected_runner(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            self._fill_source_form(pilot.app.screen)
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#sources-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#fetch", Button).press()
            await pilot.pause()
            self.assertIn("indisponible", str(pilot.app.screen.query_one("#sources-error").content))

    async def test_delete_removes_source(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            self._fill_source_form(pilot.app.screen)
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#sources-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#sources-table", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_back_button_returns_to_library_screen(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_remote_sources(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogLibraryScreen)


if __name__ == "__main__":
    unittest.main()
