# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase VII de l'interface (plan interface §12,
menu 6, §3.5/§10) : sauvegarde/restauration de configuration - creation
(avec/sans secrets), restauration, suppression, toutes destructives donc
passant par ConfirmScreen."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Checkbox, DataTable, Input

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.backup_screen import BackupScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiBackup(unittest.IsolatedAsyncioTestCase):
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
        return DependencyContainer(project_root=self.root, **kwargs)

    def _generate_config(self, container: DependencyContainer) -> None:
        generate_default_config(container.configuration, container.filesystem, container.config_file)

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_backup_screen(self, pilot) -> None:
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#backup", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, BackupScreen)

    async def test_create_config_only_backup_no_confirmation_needed(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            pilot.app.screen.query_one("#description-input", Input).value = "d1"
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, BackupScreen)
            self.assertEqual(str(pilot.app.screen.query_one("#backup-error").content), "")
            table = pilot.app.screen.query_one("#backups-table", DataTable)
            self.assertEqual(table.row_count, 1)

    async def test_create_with_secrets_requires_confirmation(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            pilot.app.screen.query_one("#include-auth", Checkbox).value = True
            await pilot.pause()
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, BackupScreen)
            table = pilot.app.screen.query_one("#backups-table", DataTable)
            self.assertEqual(table.row_count, 1)

    async def test_create_with_secrets_cancelled_creates_nothing(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            pilot.app.screen.query_one("#include-certificates", Checkbox).value = True
            await pilot.pause()
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#backups-table", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_restore_requires_confirmation_and_overwrites_config(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()

            container.config_file.write_text("CORRUPTED")

            table = pilot.app.screen.query_one("#backups-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#restore", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#backup-error").content), "")
        self.assertIn('"version"', container.config_file.read_text())

    async def test_delete_requires_confirmation_and_removes_row(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()

            table = pilot.app.screen.query_one("#backups-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#backups-table", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_delete_cancelled_keeps_row(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()

            table = pilot.app.screen.query_one("#backups-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#backups-table", DataTable)
            self.assertEqual(table.row_count, 1)

    async def test_restore_and_delete_disabled_until_row_selected(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            self.assertTrue(pilot.app.screen.query_one("#restore", Button).disabled)
            self.assertTrue(pilot.app.screen.query_one("#delete", Button).disabled)

    async def test_back_button_returns_home(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_backup_screen(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)


if __name__ == "__main__":
    unittest.main()
