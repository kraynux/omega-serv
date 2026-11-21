# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant de profil personnalise (projets 3.0.0 §B, §7.1) : verification en direct, enregistrement seulement
quand tout est bon, liste et suppression dans l'ecran Profils. Projet temporaire seulement."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.custom_profile_screen import CustomProfileScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.profiles_screen import ProfilesScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiCustomProfile(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        container = DependencyContainer(project_root=self.root)
        generate_default_config(container.configuration, container.filesystem, container.config_file)

    def tearDown(self):
        self._tmp.cleanup()

    async def _profiles(self, pilot):
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#profiles", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ProfilesScreen)

    async def test_create_accept_each_hole_save_then_delete(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(120, 60)) as pilot:
            await self._profiles(pilot)
            pilot.app.screen.query_one("#create-custom", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            self.assertIsInstance(screen, CustomProfileScreen)
            screen.query_one("#name-input", Input).value = "St"  # trop court
            screen.query_one("#label-input", Input).value = "Mon site"
            await pilot.pause()
            self.assertIn("3 à 32", str(screen.query_one("#name-error", Static).content))
            self.assertTrue(screen.query_one("#save", Button).disabled)
            screen.query_one("#name-input", Input).value = "standard"  # nom d'un profil fourni
            await pilot.pause()
            self.assertIn("déjà", str(screen.query_one("#name-error", Static).content))
            screen.query_one("#name-input", Input).value = "mon-site"
            screen.query_one("#choice-fastcgi", Select).value = "on"
            screen.query_one("#choice-methods", Select).value = "read"
            await pilot.pause()
            self.assertIn("FastCGI", str(screen.query_one("#blocking", Static).content))  # trou bloquant
            screen.query_one("#choice-methods", Select).value = "forms"
            await pilot.pause()
            boxes = list(screen.query("#accept-box Checkbox").results(Checkbox))
            self.assertTrue(boxes)
            self.assertTrue(screen.query_one("#save", Button).disabled)  # rien n'est encore accepte
            for box in boxes:
                box.value = True
                await pilot.pause()
            self.assertFalse(screen.query_one("#save", Button).disabled)
            screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ProfilesScreen)
            table = pilot.app.screen.query_one("#profiles-table", DataTable)
            self.assertEqual(table.row_count, 5)
            saved = json.loads((self.root / "config" / "profiles" / "custom" / "mon-site.json").read_text())
            self.assertEqual((saved["label"], saved["custom"]), ("Mon site", True))
            self.assertTrue(saved["options"]["fastcgi"]["enabled"])

            table.move_cursor(row=4)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-custom", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#profiles-table", DataTable).row_count, 4)

    async def test_provided_profiles_cannot_be_deleted(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._profiles(pilot)
            table = pilot.app.screen.query_one("#profiles-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            self.assertTrue(pilot.app.screen.query_one("#delete-custom", Button).disabled)


if __name__ == "__main__":
    unittest.main()
