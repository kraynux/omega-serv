"""Tests d'integration de l'ecran Reglages (retour utilisateur round 2,
2026-09-09) : theme, profil de rendu, chemins d'export/captures d'ecran,
purge. Accessible via le raccourci clavier 'o' ET, depuis le passage du
menu principal a 2 colonnes (retour utilisateur), le bouton "OPTIONS" -
memes deux voies vers le meme ecran, jamais duplique."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from omega_lib.theme.policies import TUI_THEMES
from textual.widgets import Button, Input, Select

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.settings_screen import SettingsScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiSettings(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self) -> DependencyContainer:
        return DependencyContainer(project_root=self.root)

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_settings(self, pilot) -> None:
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        await pilot.press("o")
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, SettingsScreen)

    async def test_o_shortcut_opens_settings_from_home(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_settings(pilot)

    async def test_options_button_opens_settings_from_home(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            self.assertIsInstance(pilot.app.screen, HomeScreen)
            await pilot.click("#options")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, SettingsScreen)

    async def test_exports_and_screenshots_fields_prefilled_with_defaults(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_settings(pilot)
            self.assertEqual(
                pilot.app.screen.query_one("#exports-dir-input", Input).value,
                str(container.default_exports_dir),
            )
            self.assertEqual(
                pilot.app.screen.query_one("#screenshots-dir-input", Input).value,
                str(container.default_screenshots_dir),
            )

    async def test_changing_exports_dir_persists_override(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_settings(pilot)
            new_dir = str(self.root / "custom-exports")
            pilot.app.screen.query_one("#exports-dir-input", Input).value = new_dir
            await pilot.pause()
        self.assertEqual(container.settings_store.get("exports_dir_override", ""), new_dir)

    async def test_theme_select_changes_active_theme(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_settings(pilot)
            current = pilot.app.theme
            other = next(name for name in TUI_THEMES if name != current)
            pilot.app.screen.query_one("#theme-select", Select).value = other
            await pilot.pause()
            self.assertEqual(pilot.app.theme, other)

    async def test_clear_exports_requires_confirmation(self):
        container = self._container()
        (container.default_exports_dir).mkdir(parents=True)
        (container.default_exports_dir / "leftover.json").write_text("{}")
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_settings(pilot)
            pilot.app.screen.query_one("#clear-exports", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
        self.assertFalse((container.default_exports_dir / "leftover.json").exists())

    async def test_clear_screenshots_cancelled_keeps_files(self):
        container = self._container()
        container.default_screenshots_dir.mkdir(parents=True)
        (container.default_screenshots_dir / "shot.svg").write_text("<svg/>")
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_settings(pilot)
            pilot.app.screen.query_one("#clear-screenshots", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
        self.assertTrue((container.default_screenshots_dir / "shot.svg").exists())

    async def test_back_button_returns_home(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_settings(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)


if __name__ == "__main__":
    unittest.main()
