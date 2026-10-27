"""Choix de la langue dans l'interface (OMEGA-SERV_PLAN-DETAILLE_I18N.md lot 2, §5.3/§5.4) :
libelle "Langue / Language" jamais traduit, Francais en tete, confirmation puis demande de
redemarrage de l'INTERFACE (jamais le service), annulation sans effet, splash de confirmation
dans la nouvelle langue, message de repli si la langue demandee est indisponible."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from omega_lib.i18n.policies import PSEUDO_LANGUAGE_CODE, language_for
from textual.widgets import Select, Static

from omega_serv.application.terminal.select_language import LANGUAGE_CHANGED_ENV_VAR, LANGUAGE_KEY
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.i18n import DOMAIN, STATE
from omega_serv.infrastructure.i18n.gettext_language_catalog import GettextLanguageCatalog
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.language_changed_splash_screen import (
    LanguageChangedSplashScreen,
)
from omega_serv.interfaces.tui.screens.settings_screen import SettingsScreen
from omega_serv.interfaces.tui.screens.splash import SplashScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.ports.language_catalog_port import LanguageCatalogPort
from tests.unit.test_select_language import write_mo

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiLanguage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "projet"
        (self.root / "webroot").mkdir(parents=True)
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.locale = Path(self._tmp.name) / "locale"
        write_mo(self.locale / "en" / "LC_MESSAGES" / f"{DOMAIN}.mo", {"Retour": "Back"}, status="validated")
        write_mo(self.locale / "es" / "LC_MESSAGES" / f"{DOMAIN}.mo", {"Retour": "Volver"})

    def tearDown(self):
        STATE.reset()
        os.environ.pop(LANGUAGE_CHANGED_ENV_VAR, None)
        self._tmp.cleanup()

    def _container(self) -> DependencyContainer:
        container = DependencyContainer(project_root=self.root)
        catalog: LanguageCatalogPort = GettextLanguageCatalog(self.locale)
        container._language_catalog = catalog
        return container

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_settings(self, pilot) -> None:
        await self._start(pilot)
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        await pilot.press("o")
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, SettingsScreen)

    async def test_selector_label_never_translated_and_french_first(self):
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open_settings(pilot)
            labels = [str(w.render()) for w in pilot.app.screen.query(Static)]
            self.assertIn("Langue / Language", labels)
            select = pilot.app.screen.query_one("#language-select", Select)
            self.assertEqual(select.value, "fr")
            options = list(select._options)
            self.assertEqual([value for _label, value in options], ["fr", "en", "es"])
            self.assertEqual(str(options[0][0]), "Français")
            self.assertEqual(str(options[1][0]), "English")
            self.assertEqual(str(options[2][0]), "Español (en test)")

    async def test_confirm_requests_interface_restart_and_saves_choice(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open_settings(pilot)
            pilot.app.screen.query_one("#language-select", Select).value = "en"
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            await pilot.click("#confirm")
            await pilot.pause()
        self.assertIsNotNone(app.pending_restart)
        self.assertEqual(app.pending_restart.language_code, "en")
        self.assertIsNone(app.pending_switch)
        self.assertEqual(container.settings_store.get(LANGUAGE_KEY), "en")
        self.assertEqual(STATE.language.code, "fr", "jamais de bascule a chaud : le nouveau processus l'appliquera")

    async def test_cancel_restores_selection_and_changes_nothing(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open_settings(pilot)
            pilot.app.screen.query_one("#language-select", Select).value = "es"
            await pilot.pause()
            await pilot.click("#cancel")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, SettingsScreen)
            self.assertEqual(pilot.app.screen.query_one("#language-select", Select).value, "fr")
            self.assertIsNone(app.pending_restart)
        self.assertIn(container.settings_store.get(LANGUAGE_KEY), (None, ""))

    async def test_restarted_interface_shows_language_splash_in_new_language(self):
        STATE.install(language_for(PSEUDO_LANGUAGE_CODE), GettextLanguageCatalog(self.locale).load(PSEUDO_LANGUAGE_CODE))
        os.environ[LANGUAGE_CHANGED_ENV_VAR] = PSEUDO_LANGUAGE_CODE
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LanguageChangedSplashScreen)
            prompt = str(pilot.app.screen.query_one("#language-prompt", Static).render())
            self.assertEqual(prompt, "⟦Cliquez ou appuyez sur une touche pour continuer...⟧")
            name = str(pilot.app.screen.query_one("#language-name", Static).render())
            self.assertEqual(name, "Langue / Language : Test ⟦…⟧ (développement)")
            self.assertNotIn(LANGUAGE_CHANGED_ENV_VAR, os.environ, "consommee des la lecture")
            await self._start(pilot)
            self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_normal_start_keeps_standard_splash(self):
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, SplashScreen)
            texts = [str(w.render()) for w in pilot.app.screen.query(Static)]
            self.assertIn("Cliquez ou appuyez sur une touche pour continuer...", texts)

    async def test_every_start_splash_prompt_follows_chosen_language(self):
        # Retour utilisateur 2026-10-21 : l'invite du splash NORMAL (chaque demarrage, pas
        # seulement apres un changement de langue) doit etre dans la langue choisie.
        STATE.install(language_for(PSEUDO_LANGUAGE_CODE), GettextLanguageCatalog(self.locale).load(PSEUDO_LANGUAGE_CODE))
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, SplashScreen)
            texts = [str(w.render()) for w in pilot.app.screen.query(Static)]
            self.assertIn("⟦Cliquez ou appuyez sur une touche pour continuer...⟧", texts)

    async def test_fallback_to_french_is_reported_once(self):
        STATE.install(language_for("fr"), None, fell_back_from="ru")
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertIn("Langue « ru » indisponible : interface en français.", messages)


if __name__ == "__main__":
    unittest.main()
