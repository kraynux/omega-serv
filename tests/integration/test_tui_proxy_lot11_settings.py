# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 11 : champs d'ecran des options ajoutees pendant le chantier.

- ecran Reverse proxy : « Réglages communs » (engine P8, max_response_body_mb D23, budgets C2 du lot 3) et champ de
  zone `websocket_idle_timeout_seconds` (lot 10) ;
- ecran WAF - Modules : `inspect.body_max_inspect_bytes` et `inspect.body_over_limit` (lot 2).

Toujours dans un projet temporaire : jamais le vrai `config/` ni le vrai `var/`."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Input, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.proxy_zone import parse_proxy_zones
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.reverse_proxy_screen import ReverseProxyScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.screens.waf_modules_screen import WafModulesScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestLot11Settings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(project_root=self.root)
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)
        config = self._config()
        options = dict(config.options)
        options["reverse_proxy"] = Option(name="reverse_proxy", enabled=True, settings={"zones": [
            {"url_prefix": "/ws/", "websocket_enabled": True, "upstreams": [{"host": "127.0.0.1", "port": 9}]}]})
        options["waf"] = Option(name="waf", enabled=False, settings={"mode": "block"})
        self.container.configuration.save(self.container.config_file, replace(config, options=options))

    async def asyncTearDown(self):
        self._tmp.cleanup()

    def _config(self):
        result = load_config(self.container.configuration, self.container.config_file)
        assert result.config is not None
        return result.config

    async def _home(self, pilot):
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        while not isinstance(pilot.app.screen, HomeScreen):
            await pilot.press("escape")
            await pilot.pause()

    async def _fill_and_confirm(self, pilot, values):
        self.assertIsInstance(pilot.app.screen, DynamicFormScreen)
        for field_id, value in values.items():
            pilot.app.screen.query_one(f"#df-{field_id}", Input).value = value
        pilot.app.screen.query_one("#confirm", Button).press()
        await pilot.pause()

    async def test_common_settings_are_saved_and_validated(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(140, 50)) as pilot:
            await self._home(pilot)
            await pilot.app.push_screen(ReverseProxyScreen(container=DependencyContainer(project_root=self.root)))
            await pilot.pause()
            pilot.app.screen.query_one("#general-settings", Button).press()
            await pilot.pause()
            form = pilot.app.screen
            self.assertEqual(form.query_one("#df-engine", Input).value, "auto")
            self.assertEqual(form.query_one("#df-max_response_body_mb", Input).value, "256")
            self.assertEqual(form.query_one("#df-max_pending_body_mb", Input).value, "128")
            # Refus : moins que server.max_request_size (10 Mio par defaut) - rien n'est ecrit.
            await self._fill_and_confirm(pilot, {"max_pending_body_mb": "4"})
            # Lot V (2026-11-15) : le formulaire reste ouvert, saisie gardee, erreur dedans.
            self.assertIsInstance(pilot.app.screen, DynamicFormScreen)
            self.assertIn("max_request_size", str(pilot.app.screen.query_one("#df-error", Static).content))
            self.assertEqual(pilot.app.screen.query_one("#df-max_pending_body_mb", Input).value, "4")
            self.assertNotIn("max_pending_body_mb", self._config().options["reverse_proxy"].settings)
            await self._fill_and_confirm(pilot, {"engine": "python", "max_response_body_mb": "64",
                                                 "max_pending_body_mb": "32", "max_concurrent_inspections": "8",
                                                 "max_upstream_connections": "100"})
            settings = self._config().options["reverse_proxy"].settings
            self.assertEqual((settings["engine"], settings["max_response_body_mb"], settings["max_pending_body_mb"],
                              settings["max_concurrent_inspections"], settings["max_upstream_connections"]),
                             ("python", 64, 32, 8, 100))
            self.assertEqual(len(settings["zones"]), 1)  # zones gardees

    async def test_screen_shows_settings_engine_and_always_visible_buttons(self):
        """Retour de l'auteur du 2026-11-14 : reglages en vigueur visibles sans ouvrir le formulaire, moteur par zone,
        boutons hors de la zone qui defile (visibles en 80x24)."""
        config = self._config()
        options = dict(config.options)
        options["reverse_proxy"] = Option(name="reverse_proxy", enabled=True, settings={"zones": [
            {"url_prefix": "/app/", "upstreams": [{"host": "127.0.0.1", "port": 9}]},
            {"url_prefix": "/cache/", "cache_enabled": True, "upstreams": [{"host": "127.0.0.1", "port": 9}]}]})
        self.container.configuration.save(self.container.config_file, replace(
            config, options=options, server=replace(config.server, engine="native")))
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(80, 24)) as pilot:
            await self._home(pilot)
            await pilot.app.push_screen(ReverseProxyScreen(container=DependencyContainer(project_root=self.root)))
            await pilot.pause()
            screen = pilot.app.screen
            summary = str(screen.query_one("#proxy-common-summary", Static).content)
            for expected in ("auto", "128", "64", "512", "256"):
                self.assertIn(expected, summary)
            table = screen.query_one("#proxy-zones-table", DataTable)
            self.assertEqual([table.get_row_at(i)[-1] for i in range(table.row_count)], ["natif", "Python (cache)"])
            for button_id in ("#add", "#general-settings", "#back"):
                button = screen.query_one(button_id, Button)
                self.assertFalse(any(isinstance(node, VerticalScroll) for node in button.ancestors), button_id)
                self.assertLess(button.region.bottom, 24, button_id)
                self.assertGreater(button.region.height, 0, button_id)
            # Apres « Réglages communs », le resume et la colonne suivent sans quitter l'ecran.
            screen.query_one("#general-settings", Button).press()
            await pilot.pause()
            await self._fill_and_confirm(pilot, {"engine": "python"})
            screen = pilot.app.screen
            self.assertIn("python", str(screen.query_one("#proxy-common-summary", Static).content))
            table = screen.query_one("#proxy-zones-table", DataTable)
            self.assertEqual([table.get_row_at(i)[-1] for i in range(table.row_count)],
                             ["Python (réglage)", "Python (réglage)"])

    async def test_zone_form_has_the_websocket_idle_timeout(self):
        screen = ReverseProxyScreen(container=self.container)
        zone = parse_proxy_zones(self._config().options["reverse_proxy"].settings["zones"])[0]
        fields = {field_id: default for field_id, _label, default in screen._fields_for(zone)}
        self.assertEqual(fields["websocket_idle_timeout_seconds"], "3600")
        fields["websocket_idle_timeout_seconds"] = "90"
        self.assertEqual(screen._zone_from_values(fields).websocket_idle_timeout_seconds, 90.0)

    async def test_waf_inspect_fields(self):
        app = OmegaServApp(DependencyContainer(project_root=self.root))
        async with app.run_test(size=(140, 50)) as pilot:
            await self._home(pilot)
            await pilot.app.push_screen(WafModulesScreen(container=DependencyContainer(project_root=self.root)))
            await pilot.pause()
            screen = pilot.app.screen
            self.assertEqual(screen.query_one("#body-max-inspect-input", Input).value, "65536")
            self.assertEqual(screen.query_one("#body-over-limit-input", Input).value, "pass")
            screen.query_one("#body-over-limit-input", Input).value = "refuser"
            screen.query_one("#save-mode", Button).press()
            await pilot.pause()
            self.assertNotIn("inspect", self._config().options["waf"].settings)
            screen.query_one("#body-max-inspect-input", Input).value = "131072"
            screen.query_one("#body-over-limit-input", Input).value = "reject"
            screen.query_one("#save-mode", Button).press()
            await pilot.pause()
            inspect = self._config().options["waf"].settings["inspect"]
            self.assertEqual((inspect["body_max_inspect_bytes"], inspect["body_over_limit"]), (131072, "reject"))


if __name__ == "__main__":
    unittest.main()
