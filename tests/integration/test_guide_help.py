# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration du guide d'aide (OMEGA-SERV_PLAN-DETAILLE_GUIDE_
AIDE.md, Phase 0) : aide contextuelle (`F1`), menu Guide navigable (`a`),
FAQ - meme discipline unittest/Pilot que le reste de la suite TUI.

`F1` plutot que `?` (choix initial du plan, corrige en le testant
reellement) : la plupart des ecrans de configuration ont un `Input`
autofocus au montage, qui intercepte tout caractere IMPRIMABLE (dont
`?`) comme saisie de texte avant meme que le binding d'ecran ne soit
atteint - verifie reellement (`bind-input` recevait "127.0.0.1?" au
lieu de declencher l'aide). F1 est une touche fonction, jamais
consommee par un champ de texte."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.faq_screen import FaqScreen
from omega_serv.interfaces.tui.screens.guide_detail_screen import GuideDetailScreen
from omega_serv.interfaces.tui.screens.guide_menu_screen import GuideMenuScreen
from omega_serv.interfaces.tui.screens.help_screen import HelpScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _export_guide_html(screen_guides, faq_entries, theme_name):
    from omega_serv.infrastructure.exporters.html_exporter import export_guide_html

    return export_guide_html(screen_guides, faq_entries, theme_name)


class TestGuideHelp(unittest.IsolatedAsyncioTestCase):
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
        return DependencyContainer(project_root=self.root, export_guide_html_fn=_export_guide_html)

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def test_contextual_help_opens_the_screen_own_fiche(self):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            pilot.app.screen.query_one("#server-config", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
            pilot.app.screen.query_one("#base", Button).press()
            await pilot.pause()
            await pilot.press("f1")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideDetailScreen)
            self.assertIn("CONFIGURATION DE BASE", str(pilot.app.screen.query_one(".omega-title").content))

    async def test_contextual_help_works_on_home_screen(self):
        # HomeScreen n'herite pas de OmegaScreen (echap y a un role
        # different) - verifie que l'aide contextuelle fonctionne quand
        # meme, via show_contextual_help() partagee (_base.py).
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await pilot.press("f1")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideDetailScreen)
            self.assertIn("ACCUEIL", str(pilot.app.screen.query_one(".omega-title").content))

    async def test_contextual_help_works_on_wizard_welcome_screen(self):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            pilot.app.screen.query_one("#wizard", Button).press()
            await pilot.pause()
            await pilot.press("f1")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideDetailScreen)
            self.assertIn("BIENVENUE", str(pilot.app.screen.query_one(".omega-title").content))

    async def test_contextual_help_falls_back_to_help_screen_when_undocumented(self):
        # Les 64 ecrans reels sont maintenant tous documentes (Phase 9) -
        # ce test verifie donc le mecanisme de repli lui-meme via un
        # ecran synthetique, jamais reference dans SCREEN_GUIDES, plutot
        # que de dependre d'un vrai ecran "pas encore documente" qui n'existe
        # plus. Meme fonction reelle (_base.py::show_contextual_help) que
        # pour tout ecran reel.
        class _NeverDocumentedTestScreen(OmegaScreen):
            def compose(self) -> ComposeResult:
                yield Static("test")

        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await pilot.app.push_screen(_NeverDocumentedTestScreen())
            await pilot.pause()
            await pilot.press("f1")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HelpScreen)

    async def test_guide_menu_opens_via_a_and_navigates_to_a_documented_fiche(self):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await pilot.press("a")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideMenuScreen)
            table = pilot.app.screen.query_one("#guide-menu-table", DataTable)
            self.assertGreater(table.row_count, 0)
            # "Options" est documentee des la Phase 0 (ecran pilote).
            options_row = next(
                i for i in range(table.row_count) if table.get_row_at(i)[1] == "Options"
            )
            table.move_cursor(row=options_row)
            table.action_select_cursor()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideDetailScreen)

    async def test_guide_menu_notifies_instead_of_navigating_when_undocumented(self):
        # Les 64 entrees du menu sont maintenant toutes documentees
        # (Phase 9) - simule une entree non documentee en retirant
        # temporairement une fiche du registre (patch.dict la restaure
        # automatiquement), plutot que de dependre d'un vrai "A venir"
        # qui n'existe plus.
        from unittest.mock import patch

        from omega_serv.interfaces.tui.guide.registry import SCREEN_GUIDES

        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        with patch.dict(SCREEN_GUIDES):
            del SCREEN_GUIDES["OptionsScreen"]
            await self._run_undocumented_notification_check(app)

    async def _run_undocumented_notification_check(self, app: OmegaServApp) -> None:
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await pilot.press("a")
            await pilot.pause()
            table = pilot.app.screen.query_one("#guide-menu-table", DataTable)
            undocumented_row = next(
                i for i in range(table.row_count) if table.get_row_at(i)[2] == "A venir"
            )
            table.move_cursor(row=undocumented_row)
            table.action_select_cursor()
            await pilot.pause()
            # Reste sur le menu Guide - jamais de navigation vers une fiche inexistante.
            self.assertIsInstance(pilot.app.screen, GuideMenuScreen)
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("pas encore documente" in m for m in messages))

    async def test_faq_screen_opens_from_guide_menu_and_lists_entries(self):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await pilot.press("a")
            await pilot.pause()
            pilot.app.screen.query_one("#faq", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, FaqScreen)

    async def test_export_html_writes_a_file_with_documented_screens_and_faq(self):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await pilot.press("a")
            await pilot.pause()
            pilot.app.screen.query_one("#export-html", Button).press()
            await pilot.pause()

        exports = list(container.default_exports_dir.glob("guide-export.*.html"))
        self.assertEqual(len(exports), 1)
        content = exports[0].read_text(encoding="utf-8")
        self.assertIn("Guide d'aide complet", content)
        self.assertIn("CONFIGURATION DE BASE", content.upper())
        self.assertIn("Pourquoi mon option activ", content)


if __name__ == "__main__":
    unittest.main()
