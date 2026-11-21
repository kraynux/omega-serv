# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot V (decision de l'auteur du 2026-11-15, projets 3.0.0 §7.1 et §7.9) : une saisie refusee ne ferme plus le
formulaire. L'explication s'affiche dans le formulaire, ce qui a ete tape est garde ; les doublons et les reponses
oui/non mal tapees sont refuses au lieu d'etre enregistres en silence.

Toujours dans un projet temporaire : jamais le vrai config/ ni le vrai var/."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, DataTable, Input, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.security_screen import SecurityScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestLotVFormValidation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot" / "media").mkdir(parents=True)
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(project_root=self.root)
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)

    def tearDown(self):
        self._tmp.cleanup()

    async def _open(self, pilot, button_id: str) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one(f"#{button_id}", Button).press()
        await pilot.pause()

    async def _submit(self, pilot, values: dict[str, str]) -> None:
        for field_id, value in values.items():
            pilot.app.screen.query_one(f"#df-{field_id}", Input).value = value
        pilot.app.screen.query_one("#confirm", Button).press()
        await pilot.pause()

    def _form_error(self, pilot) -> str:
        self.assertIsInstance(pilot.app.screen, DynamicFormScreen)
        return str(pilot.app.screen.query_one("#df-error", Static).content)

    async def test_invalid_alias_keeps_the_form_open_with_the_input(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open(pilot, "aliases")
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            await self._submit(pilot, {"url_prefix": "media/", "target_path": "webroot/media",
                                       "allow_outside_webroot": "non"})
            self.assertIn("Erreur", self._form_error(pilot))
            self.assertEqual(pilot.app.screen.query_one("#df-target_path", Input).value, "webroot/media")
            await self._submit(pilot, {"url_prefix": "/media/"})  # correction de la seule faute
            self.assertNotIsInstance(pilot.app.screen, DynamicFormScreen)
            self.assertEqual(pilot.app.screen.query_one("#aliases-table", DataTable).row_count, 1)

    async def test_duplicate_alias_is_refused(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open(pilot, "aliases")
            for _round in range(2):
                pilot.app.screen.query_one("#add", Button).press()
                await pilot.pause()
                await self._submit(pilot, {"url_prefix": "/media/", "target_path": "webroot/media",
                                           "allow_outside_webroot": "non"})
            self.assertIn("Doublon", self._form_error(pilot))
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#aliases-table", DataTable).row_count, 1)

    async def test_mistyped_yes_no_is_refused_instead_of_meaning_no(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open(pilot, "aliases")
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            await self._submit(pilot, {"url_prefix": "/m/", "target_path": "webroot/media",
                                       "allow_outside_webroot": "ouii"})
            error = self._form_error(pilot)
            self.assertIn("ouii", error)
            self.assertIn("oui", error)

    async def test_inline_yes_no_field_is_checked_on_save(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open(pilot, "security")
            self.assertIsInstance(pilot.app.screen, SecurityScreen)
            before = self.container.config_file.read_text()
            pilot.app.screen.query_one("#hsts-preload-input", Input).value = "peut-etre"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("peut-etre", str(pilot.app.screen.query_one("#form-error", Static).content))
            self.assertEqual(self.container.config_file.read_text(), before)

    async def test_redirect_code_error_stays_in_the_form(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open(pilot, "redirects")
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            await self._submit(pilot, {"url_prefix": "/old/", "destination": "/new/", "status_code": "30l"})
            self.assertIn("30l", self._form_error(pilot))
            self.assertEqual(pilot.app.screen.query_one("#df-destination", Input).value, "/new/")


if __name__ == "__main__":
    unittest.main()
