"""Tests d'integration Phase II de l'interface (plan interface §12,
menu 2) : profils (liste, detail, application avec diff) et options
(liste, bascule) - conteneur reel, aucun mock."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, DataTable

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.apply_profile_screen import ApplyProfileScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.options_screen import OptionsScreen
from omega_serv.interfaces.tui.screens.profiles_screen import ProfilesScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiProfilesAndOptions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(project_root=self.root)
        self.config_path = self.root / "config" / "omega-serve.json"
        generate_default_config(self.container.configuration, self.container.filesystem, self.config_path)

    def tearDown(self):
        self._tmp.cleanup()

    async def _reach_home(self, pilot):
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_profiles_screen_lists_all_known_profiles(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            pilot.app.screen.query_one("#profiles", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ProfilesScreen)
            table = pilot.app.screen.query_one("#profiles-table", DataTable)
            self.assertEqual(table.row_count, 4)

    async def test_selecting_profile_shows_detail_and_enables_apply(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            pilot.app.screen.query_one("#profiles", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#profiles-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            apply_button = pilot.app.screen.query_one("#apply", Button)
            self.assertFalse(apply_button.disabled)
            self.assertIn("development", str(pilot.app.screen.query_one("#profile-detail").content))

    async def test_apply_profile_shows_diff_and_writes_config_on_confirm(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            pilot.app.screen.query_one("#profiles", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#profiles-table", DataTable)
            table.move_cursor(row=0)  # "development" (ordre alphabetique)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#apply", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ApplyProfileScreen)
            plan_text = str(pilot.app.screen.query_one("#plan-text").content)
            self.assertIn("Modifications", plan_text)

            pilot.app.screen.query_one("#apply", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ProfilesScreen)

        data = self.config_path.read_text()
        self.assertIn('"profile": "development"', data)

    async def _open_options(self, pilot) -> None:
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
        pilot.app.screen.query_one("#options", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, OptionsScreen)

    async def test_options_screen_lists_all_known_options(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            self.assertEqual(table.row_count, 14)

    async def test_enabling_option_persists_and_refreshes_table(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            table.move_cursor(row=0)  # "access_control" (ordre alphabetique)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            self.assertEqual(list(table.get_row_at(0)), ["access_control", "actif"])

        data = self.config_path.read_text()
        self.assertIn('"access_control"', data)

    async def test_enabling_fastcgi_first_time_warns_restart_required(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            fastcgi_row = next(i for i in range(table.row_count) if table.get_row_at(i)[0] == "fastcgi")
            table.move_cursor(row=fastcgi_row)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m and "PREMIERE activation" in m for m in messages))

    async def test_enabling_reverse_proxy_first_time_warns_restart_required(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            proxy_row = next(i for i in range(table.row_count) if table.get_row_at(i)[0] == "reverse_proxy")
            table.move_cursor(row=proxy_row)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m and "PREMIERE activation" in m for m in messages))

    async def test_enabling_non_fastcgi_option_never_warns_restart(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            table.move_cursor(row=0)  # "access_control"
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertFalse(any("REDEMARRAGE COMPLET" in m for m in messages))
            self.assertTrue(any("Rechargez" in m for m in messages))

    async def test_disabling_fastcgi_never_triggers_first_enable_warning(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            fastcgi_row = next(i for i in range(table.row_count) if table.get_row_at(i)[0] == "fastcgi")
            table.move_cursor(row=fastcgi_row)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            pilot.app._notifications.clear()
            table.move_cursor(row=fastcgi_row)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#disable", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertFalse(any("REDEMARRAGE COMPLET" in m for m in messages))

    async def test_enabling_active_defense_warns_restart_required(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            row = next(i for i in range(table.row_count) if table.get_row_at(i)[0] == "active_defense")
            table.move_cursor(row=row)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m and "JAMAIS recharge" in m for m in messages))

    async def test_disabling_active_defense_also_warns_restart_required(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_options(pilot)
            table = pilot.app.screen.query_one("#options-table", DataTable)
            row = next(i for i in range(table.row_count) if table.get_row_at(i)[0] == "active_defense")
            table.move_cursor(row=row)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            pilot.app._notifications.clear()
            table.move_cursor(row=row)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#disable", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m and "JAMAIS recharge" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
