"""Aide -> Contact et support (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b) : navigation depuis le Guide
d'aide, ouverture des adresses (cafe, formulaire de contact), declaration (mode obligatoire, message
exact affiche, envoi, echec en mode « une seule fois »), puis retrait confirme. Stockage reel sous
un dossier temporaire ; doubles seulement pour l'envoi HTTPS et le navigateur."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Select, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.contact_support_screen import (
    CONTACT_FORM_URL,
    PAYPAL_URL,
    ContactSupportScreen,
)
from omega_serv.interfaces.tui.screens.declaration_screen import DeclarationScreen, country_options
from omega_serv.interfaces.tui.screens.guide_menu_screen import GuideMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.ports.declaration_port import SendOutcome

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _Sender:
    def __init__(self) -> None:
        self.ok = True
        self.sent: list[dict] = []

    def send(self, payload: dict) -> SendOutcome:
        self.sent.append(dict(payload))
        return SendOutcome(True) if self.ok else SendOutcome(False, "unreachable")


class _ReleaseSource:
    def __init__(self, content: str | None) -> None:
        self.content = content

    def fetch_sha_list(self) -> str | None:
        return self.content


class TestContactSupport(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        (self.root / "pyproject.toml").write_text('version = "2.5.0"\n', encoding="utf-8")
        self.sender = _Sender()
        self.release_source = _ReleaseSource("aa  omega-serv-2.5.0.tar.gz\nbb  omega-serv-2.6.0.tar.gz\n")
        self.opened: list[str] = []
        self.container = DependencyContainer(
            project_root=self.root,
            declaration_sender_factory=lambda _version: self.sender,
            release_source_factory=lambda _version: self.release_source,
            url_opener=lambda url: self.opened.append(url) or True,
        )
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)

    def tearDown(self):
        self._tmp.cleanup()

    async def _open_contact(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, GuideMenuScreen)
        pilot.app.screen.query_one("#contact-support", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ContactSupportScreen)

    async def _wait_for(self, pilot, condition) -> None:
        for _attempt in range(50):
            await pilot.pause(0.05)
            if condition():
                return
        self.fail("condition jamais atteinte")

    async def test_coffee_and_contact_open_the_browser(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open_contact(pilot)
            pilot.app.screen.query_one("#coffee", Button).press()
            await self._wait_for(pilot, lambda: len(self.opened) == 1)
            pilot.app.screen.query_one("#contact", Button).press()
            await self._wait_for(pilot, lambda: len(self.opened) == 2)
            self.assertEqual(self.opened, [PAYPAL_URL, CONTACT_FORM_URL])
            self.assertTrue(pilot.app.screen.query_one("#withdraw", Button).disabled)

    async def test_check_update_shows_new_version_and_opens_release_notes(self):
        """Verification manuelle (2026-11-07) : version 2.5.0 installee, 2.6.0 publiee."""
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open_contact(pilot)
            self.assertIn("2.5.0", str(pilot.app.screen.query_one("#update-state", Static).content))
            self.assertTrue(pilot.app.screen.query_one("#release-notes", Button).disabled)
            pilot.app.screen.query_one("#check-update", Button).press()
            await self._wait_for(pilot, lambda: not pilot.app.screen.query_one("#release-notes", Button).disabled)
            self.assertIn("2.6.0", str(pilot.app.screen.query_one("#update-state", Static).content))
            pilot.app.screen.query_one("#release-notes", Button).press()
            await self._wait_for(pilot, lambda: len(self.opened) == 1)
            self.assertTrue(self.opened[0].endswith("omega-serv-2.6.0-nouveautes.txt"))

    async def test_check_update_unreachable_site_says_so(self):
        self.release_source.content = None
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open_contact(pilot)
            pilot.app.screen.query_one("#check-update", Button).press()
            await self._wait_for(
                pilot, lambda: "injoignable" in str(pilot.app.screen.query_one("#update-state", Static).content))
            self.assertTrue(pilot.app.screen.query_one("#release-notes", Button).disabled)

    async def test_declare_then_withdraw(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open_contact(pilot)
            pilot.app.screen.query_one("#declare", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            self.assertIsInstance(screen, DeclarationScreen)
            self.assertTrue(screen.query_one("#send", Button).disabled)  # aucun mode preselectionne
            screen.query_one("#declaration-mode", Select).value = "quotidien"
            screen.query_one("#declaration-country", Select).value = "FR"
            await pilot.pause()
            self.assertFalse(screen.query_one("#send", Button).disabled)
            preview = str(screen.query_one("#declaration-preview", Static).content)
            self.assertIn('"envoi": "quotidien"', preview)
            self.assertIn('"pays": "FR"', preview)
            self.assertNotIn("continent", preview)
            screen.query_one("#send", Button).press()
            await self._wait_for(pilot, lambda: isinstance(pilot.app.screen, ContactSupportScreen))
            self.assertEqual(self.sender.sent[0]["envoi"], "quotidien")
            self.assertEqual(self.sender.sent[0]["version"], "2.5.0")
            self.assertEqual(len(self.sender.sent[0]["cle"]), 32)
            stored = json.loads((self.root / "var" / "lib" / "declaration" / "declaration.json").read_text())
            self.assertEqual(stored["pays"], "FR")
            withdraw_button = pilot.app.screen.query_one("#withdraw", Button)
            self.assertFalse(withdraw_button.disabled)
            withdraw_button.press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            await pilot.click("#confirm")
            await self._wait_for(pilot, lambda: len(self.sender.sent) == 2)
            await self._wait_for(pilot, lambda: pilot.app.screen.query_one("#withdraw", Button).disabled)
            self.assertEqual(self.sender.sent[1], {"cle": self.sender.sent[0]["cle"], "retrait": True})
            self.assertFalse((self.root / "var" / "lib" / "declaration" / "declaration.json").exists())

    async def test_once_mode_failure_keeps_the_form_and_records_nothing(self):
        self.sender.ok = False
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open_contact(pilot)
            pilot.app.screen.query_one("#declare", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            screen.query_one("#declaration-mode", Select).value = "unique"
            await pilot.pause()
            screen.query_one("#send", Button).press()
            await self._wait_for(pilot, lambda: len(self.sender.sent) == 1)
            await self._wait_for(pilot, lambda: not screen.query_one("#send", Button).disabled)
            self.assertIs(pilot.app.screen, screen)
            self.assertIn("rien", str(screen.query_one("#declaration-error", Static).content))
            self.assertFalse((self.root / "var" / "lib" / "declaration" / "declaration.json").exists())

    def test_country_list_is_localised_and_ends_with_other(self):
        options = country_options("de")
        self.assertEqual(len(options), 250)
        self.assertEqual(options[-1][1], "autre")
        self.assertIn(("Deutschland", "DE"), options)


if __name__ == "__main__":
    unittest.main()
