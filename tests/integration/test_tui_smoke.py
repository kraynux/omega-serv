"""Tests d'integration Phase I de l'interface (plan interface §12) :
demarrage complet (splash -> avertissement terminal eventuel -> accueil),
cycle de theme, aide, sortie avec confirmation. Assertions structurelles
via l'API `Pilot` de Textual, jamais de capture d'ecran - documente
ailleurs dans la suite comme peu fiable pour ce type d'interface. Meme
discipline `unittest` que le reste de la suite de tests SERV (pas de
style pytest comme CHECK/TRACK)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Static

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.guide_menu_screen import GuideMenuScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.instance_switch_splash_screen import (
    InstanceSwitchSplashScreen,
)
from omega_serv.interfaces.tui.screens.splash import SplashScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen


class TestTuiSmoke(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.container = DependencyContainer(project_root=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    async def _reach_home(self, pilot):
        """Ferme le splash (n'importe quelle touche), puis franchit
        l'avertissement terminal s'il apparait (depend de la taille
        reelle du terminal d'execution des tests)."""
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_app_reaches_home_after_splash(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)) as pilot:
            await self._reach_home(pilot)

    async def test_normal_splash_shown_without_switch_marker(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)) as pilot:
            self.assertIsInstance(pilot.app.screen, SplashScreen)

    async def test_switch_splash_shown_when_switched_from_env_var_present(self):
        os.environ["OMEGA_SERV_SWITCHED_FROM"] = "prod"
        try:
            app = OmegaServApp(self.container)
            async with app.run_test(size=(120, 40)) as pilot:
                self.assertIsInstance(pilot.app.screen, InstanceSwitchSplashScreen)
                content = "\n".join(str(widget.render()) for widget in pilot.app.screen.query(Static))
                self.assertIn("Depuis : prod", content)
                await pilot.press("x")
                await pilot.pause()
                if isinstance(pilot.app.screen, TerminalWarningScreen):
                    await pilot.click("#continue")
                    await pilot.pause()
                self.assertIsInstance(pilot.app.screen, HomeScreen)
        finally:
            os.environ.pop("OMEGA_SERV_SWITCHED_FROM", None)

    async def test_switch_marker_env_var_is_consumed_once_read(self):
        os.environ["OMEGA_SERV_SWITCHED_FROM"] = "prod"
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)):
            pass
        self.assertNotIn("OMEGA_SERV_SWITCHED_FROM", os.environ)

    async def test_help_screen_opens_and_closes(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)) as pilot:
            await self._reach_home(pilot)
            await pilot.press("a")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideMenuScreen)
            await pilot.press("escape")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_home_menu_uses_two_columns_with_all_expected_buttons(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            menu = pilot.app.screen.query_one(".omega-home-menu")
            self.assertIn("omega-home-menu-2col", menu.classes)
            button_ids = {b.id for b in pilot.app.screen.query(Button)}
            self.assertEqual(
                button_ids,
                {
                    "capabilities", "service", "wizard", "instances", "profiles", "audit",
                    "server-config", "backup", "active-defense", "help", "resource-status",
                    "options", "logs", "quit",
                },
            )

    async def test_help_button_on_home_menu_opens_the_same_guide(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)) as pilot:
            await self._reach_home(pilot)
            await pilot.click("#help")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideMenuScreen)

    async def test_theme_cycle_key_changes_theme(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)) as pilot:
            await self._reach_home(pilot)
            initial_theme = app.theme
            await pilot.press("t")
            await pilot.pause()
            self.assertNotEqual(app.theme, initial_theme)

    async def test_quit_requires_confirmation(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)) as pilot:
            await self._reach_home(pilot)
            await pilot.press("q")
            await pilot.pause()
            self.assertTrue(app.is_running)
            await pilot.click("#confirm")
        self.assertFalse(app.is_running)

    async def test_quit_button_on_home_menu_requires_confirmation(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 40)) as pilot:
            await self._reach_home(pilot)
            await pilot.click("#quit")
            await pilot.pause()
            self.assertTrue(app.is_running)
            await pilot.click("#confirm")
        self.assertFalse(app.is_running)


if __name__ == "__main__":
    unittest.main()
