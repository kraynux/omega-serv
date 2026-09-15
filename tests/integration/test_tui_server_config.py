# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase II de l'interface (plan interface §12,
menu 3, hors sous-ecran TLS §7.3 - Phase III) : configuration de base,
limites, securite generique, alias/redirections/rewrites/dirlisting/
proxies de confiance (CRUD de regles), FastCGI (enregistrement unique),
cache (zones+extensions), authentification (§7.1). WAF a demenage hors
de ce menu le 2026-09-13 (retour utilisateur : "le menu WAF va etre
sorti du menu configuration detaille... sur le MENU PRINCIPAL") - voir
test_tui_active_defense.py, qui couvre desormais l'ecran combine
"Active Securite" (Active Defense + WAF)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, DataTable, Input

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.config_check_screen import ConfigCheckScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.options_screen import OptionsScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiServerConfig(unittest.IsolatedAsyncioTestCase):
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

    async def _open_menu3(self, pilot) -> None:
        while not isinstance(pilot.app.screen, HomeScreen):
            await pilot.press("escape")
            await pilot.pause()
            if isinstance(pilot.app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
                await pilot.pause()
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def test_base_config_saves_new_values(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#base", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#port-input", Input).value = "9090"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
            # Retour utilisateur 2026-09-11 (audit reload/restart) :
            # bind/port ne se rechargent jamais a chaud - avertissement
            # explicite obligatoire quand l'un des deux change reellement.
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m for m in messages))

        data = container.config_file.read_text()
        self.assertIn('"port": 9090', data)

    async def test_base_config_no_restart_warning_when_port_unchanged(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#base", Button).press()
            await pilot.pause()
            # Seul server_name change, jamais bind/port - reste a chaud.
            pilot.app.screen.query_one("#server-name-input", Input).value = "mon-serveur"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertFalse(any("REDEMARRAGE COMPLET" in m for m in messages))

    async def test_base_config_rejects_invalid_port(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#base", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#port-input", Input).value = "not-a-number"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("invalide", str(pilot.app.screen.query_one("#form-error").content))

    async def test_limits_screen_saves_values(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#limits", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#field-max_connections", Input).value = "512"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
        self.assertIn('"max_connections": 512', container.config_file.read_text())

    async def test_limits_screen_no_restart_warning_when_backlog_unchanged(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#limits", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#field-max_connections", Input).value = "512"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertFalse(any("REDEMARRAGE COMPLET" in m for m in messages))

    async def test_limits_screen_warns_on_restart_when_backlog_changed(self):
        # Bug d'omission trouve (guide d'aide, point 4) : listen_backlog
        # est bind au socket d'ecoute au meme titre que bind/port
        # (jamais retouche par reload_scoped) - cet ecran ne le
        # signalait jamais avant correction.
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#limits", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#field-listen_backlog", Input).value = "256"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m and "listen_backlog" in m for m in messages))
        self.assertIn('"listen_backlog": 256', container.config_file.read_text())

    async def test_security_screen_saves_values(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#security", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#csp-mode-input", Input).value = "report-only"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
        self.assertIn('"csp_mode": "report-only"', container.config_file.read_text())

    async def test_aliases_full_crud_cycle(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#aliases", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/media/"
            pilot.app.screen.query_one("#df-target_path", Input).value = "webroot/media"
            pilot.app.screen.query_one("#df-allow_outside_webroot", Input).value = "non"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#aliases-table", DataTable)
            self.assertEqual(table.row_count, 1)

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#edit", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-target_path", Input).value = "webroot/media2"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn('"target_path": "webroot/media2"', container.config_file.read_text())

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#aliases-table", DataTable).row_count, 0)

    async def test_options_and_config_check_shortcuts_reach_real_screens(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#options", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, OptionsScreen)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)

            pilot.app.screen.query_one("#config-check", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfigCheckScreen)

    async def test_access_control_full_crud_cycle(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#access-control", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-path_prefix", Input).value = "/private/"
            pilot.app.screen.query_one("#df-verdict", Input).value = "deny"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#access-rules-table", DataTable)
            self.assertEqual(table.row_count, 1)

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#edit", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-path_prefix", Input).value = "/private/.assets/"
            pilot.app.screen.query_one("#df-verdict", Input).value = "allow"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn('"path_prefix": "/private/.assets/"', container.config_file.read_text())

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#access-rules-table", DataTable).row_count, 0)

    async def test_access_control_rule_with_extensions(self):
        # Retour utilisateur (guide d'aide, point 2) : deny une
        # extension sensible globalement, sauf sous un prefixe precis.
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#access-control", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-path_prefix", Input).value = "/"
            pilot.app.screen.query_one("#df-verdict", Input).value = "deny"
            pilot.app.screen.query_one("#df-extensions", Input).value = ".key, .pem"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#access-rules-table", DataTable).row_count, 1)
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("Rechargez" in m for m in messages))
        data = container.config_file.read_text()
        self.assertIn('".key"', data)
        self.assertIn('".pem"', data)

    async def test_access_control_rejects_invalid_verdict(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#access-control", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-path_prefix", Input).value = "/private/"
            pilot.app.screen.query_one("#df-verdict", Input).value = "block"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("verdict", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#access-rules-table", DataTable).row_count, 0)

    async def test_reverse_proxy_full_crud_cycle(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#reverse-proxy", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/api/"
            pilot.app.screen.query_one("#df-upstreams", Input).value = "127.0.0.1:3000"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#proxy-zones-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(list(table.get_row_at(0)), ["/api/", "127.0.0.1:3000", "Non", "Oui", "Non"])

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#edit", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-upstreams", Input).value = "127.0.0.1:4000, https://127.0.0.1:4001"
            pilot.app.screen.query_one("#df-preserve_host_header", Input).value = "oui"
            pilot.app.screen.query_one("#df-verify_upstream_tls", Input).value = "non"
            pilot.app.screen.query_one("#df-websocket_enabled", Input).value = "oui"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            config_text = container.config_file.read_text()
            self.assertIn('"port": 4000', config_text)
            self.assertIn('"use_tls": true', config_text)
            self.assertIn('"verify_upstream_tls": false', config_text)
            self.assertIn('"websocket_enabled": true', config_text)
            self.assertEqual(
                list(table.get_row_at(0)),
                ["/api/", "127.0.0.1:4000, https://127.0.0.1:4001", "Oui", "Non", "Oui"],
            )

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#proxy-zones-table", DataTable).row_count, 0)

    async def test_reverse_proxy_rejects_invalid_port(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#reverse-proxy", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/api/"
            pilot.app.screen.query_one("#df-upstreams", Input).value = "127.0.0.1:99999"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("port d'upstream invalide", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#proxy-zones-table", DataTable).row_count, 0)

    async def test_reverse_proxy_rejects_non_numeric_port(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#reverse-proxy", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/api/"
            pilot.app.screen.query_one("#df-upstreams", Input).value = "127.0.0.1:not-a-number"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("invalides", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#proxy-zones-table", DataTable).row_count, 0)

    async def test_aliases_rejects_target_outside_webroot_without_flag(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#aliases", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/files/"
            pilot.app.screen.query_one("#df-target_path", Input).value = "/etc/passwd"
            pilot.app.screen.query_one("#df-allow_outside_webroot", Input).value = "non"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("Erreur", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#aliases-table", DataTable).row_count, 0)

    async def test_redirects_full_crud_cycle(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#redirects", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/old/"
            pilot.app.screen.query_one("#df-destination", Input).value = "/new/"
            pilot.app.screen.query_one("#df-status_code", Input).value = "301"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#redirects-table", DataTable).row_count, 1)
        self.assertIn('"status_code": 301', container.config_file.read_text())

    async def test_rewrites_full_crud_cycle(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#rewrites", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-match_prefix", Input).value = "/old/"
            pilot.app.screen.query_one("#df-replacement_prefix", Input).value = "/new/"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#rewrites-table", DataTable).row_count, 1)

    async def test_dirlisting_add_and_delete(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#dirlisting", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-prefix", Input).value = "/files/"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#zones-table", DataTable)
            self.assertEqual(table.row_count, 1)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#zones-table", DataTable).row_count, 0)

    async def test_dirlisting_settings_form_saves_values(self):
        # Retour utilisateur (guide d'aide, point 1) : CSS de base +
        # header/readme configurables, sur le meme ecran que les zones
        # (jamais un sous-menu separe, cf docstring dirlisting_screen.py).
        from textual.widgets import Select

        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#dirlisting", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#theme-select", Select).value = "omega-neon"
            pilot.app.screen.query_one("#external-css-input", Input).value = "/.assets/css/folder.css"
            pilot.app.screen.query_one("#show-header-input", Input).value = "oui"
            pilot.app.screen.query_one("#save-settings", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("Rechargez" in m for m in messages))
        data = container.config_file.read_text()
        self.assertIn('"theme": "omega-neon"', data)
        self.assertIn('"external_css": "/.assets/css/folder.css"', data)
        self.assertIn('"show_header": true', data)

    async def test_trusted_proxy_networks_and_headers(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#trusted-proxy", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-network", Input).value = "10.0.0.0/8"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#networks-table", DataTable).row_count, 1)

            pilot.app.screen.query_one("#header-preference-input", Input).value = "X-Forwarded-For"
            pilot.app.screen.query_one("#save-headers", Button).press()
            await pilot.pause()
        self.assertIn('"trusted_networks"', container.config_file.read_text())
        self.assertIn('"header_preference"', container.config_file.read_text())

    async def test_trusted_proxy_rejects_invalid_network(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#trusted-proxy", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-network", Input).value = "not-a-network"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("invalide", str(pilot.app.screen.query_one("#form-error").content))

    async def test_fastcgi_saves_and_validates_outside_webroot(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#fastcgi", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#field-script_root", Input).value = "phpapp"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
        self.assertIn('"script_root": "phpapp"', container.config_file.read_text())

    async def test_fastcgi_rejects_script_root_inside_webroot(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#fastcgi", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#field-script_root", Input).value = "webroot/app"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("interdit", str(pilot.app.screen.query_one("#form-error").content))

    async def test_fastcgi_allowed_scripts_saved_and_reloaded(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#fastcgi", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#field-script_root", Input).value = "phpapp"
            pilot.app.screen.query_one("#field-allowed_scripts", Input).value = "index.php, api/router.php"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#fastcgi", Button).press()
            await pilot.pause()
            self.assertEqual(
                pilot.app.screen.query_one("#field-allowed_scripts", Input).value, "index.php, api/router.php"
            )
        self.assertIn('"allowed_scripts"', container.config_file.read_text())

    async def test_cache_zones_and_extensions_crud(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#cache", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-path_prefix", Input).value = "/static/"
            pilot.app.screen.query_one("#df-cache_control", Input).value = "public, max-age=3600"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#zones-table", DataTable).row_count, 1)

            pilot.app.screen.query_one("#add-extension", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-extension", Input).value = ".css"
            pilot.app.screen.query_one("#df-cache_control", Input).value = "public, max-age=86400"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#extensions-table", DataTable).row_count, 1)

    async def test_error_pages_screen_saves_custom_dir_and_reflects_existing_file(self):
        container = self._container()
        self._generate_config(container)
        errors_dir = self.root / "webroot" / ".errors"
        errors_dir.mkdir(parents=True)
        (errors_dir / "404.html").write_text("<html>404 personnalisee</html>")
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#error-pages", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#statuses-table", DataTable)
            self.assertEqual(list(table.get_row_at(3)), ["404", "Not Found", "Oui"])
            self.assertEqual(list(table.get_row_at(0)), ["400", "Bad Request", "Non"])

            pilot.app.screen.query_one("#dir-input", Input).value = "webroot/.errors"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

        data = container.config_file.read_text()
        self.assertIn('"custom_dir": "webroot/.errors"', data)

    async def test_error_pages_screen_warns_when_option_disabled(self):
        # Retour utilisateur 2026-09-11, vrai bug trouve : cet ecran
        # laissait configurer le repertoire de surcharge et afficher
        # "mis a jour" sans jamais indiquer que l'option restait
        # desactivee (activation geree separement via le menu Options)
        # - un fichier <statut>.html place correctement n'avait donc
        # jamais aucun effet, sans aucun indice visible dans cet ecran.
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#error-pages", Button).press()
            await pilot.pause()
            state = str(pilot.app.screen.query_one("#enabled-state").content)
            self.assertIn("DESACTIVEE", state)
            self.assertIn("Options", state)

            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            state_after_save = str(pilot.app.screen.query_one("#enabled-state").content)
            self.assertIn("DESACTIVEE", state_after_save)

    async def test_auth_add_user_create_zone_check_permissions_and_remove(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#auth", Button).press()
            await pilot.pause()

            pilot.app.screen.query_one("#add-user", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-username", Input).value = "alice"
            pilot.app.screen.query_one("#df-password", Input).value = "secretpass"
            pilot.app.screen.query_one("#df-password_confirm", Input).value = "secretpass"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("alice", str(pilot.app.screen.query_one("#auth-list").content))

            pilot.app.screen.query_one("#check-permissions", Button).press()
            await pilot.pause()
            self.assertIn("0o600", str(pilot.app.screen.query_one("#form-error").content))

            pilot.app.screen.query_one("#create-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-path_prefix", Input).value = "/admin/"
            pilot.app.screen.query_one("#df-realm", Input).value = "Admin"
            pilot.app.screen.query_one("#df-allowed_users", Input).value = "alice"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("/admin/", str(pilot.app.screen.query_one("#auth-list").content))

            pilot.app.screen.query_one("#remove-user", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-username", Input).value = "alice"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("(aucun)", str(pilot.app.screen.query_one("#auth-list").content))

    async def test_auth_rejects_mismatched_password_confirmation(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#auth", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-user", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-username", Input).value = "bob"
            pilot.app.screen.query_one("#df-password", Input).value = "one"
            pilot.app.screen.query_one("#df-password_confirm", Input).value = "two"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("correspondent", str(pilot.app.screen.query_one("#form-error").content))
            self.assertIn("(aucun)", str(pilot.app.screen.query_one("#auth-list").content))

    async def test_back_buttons_return_to_menu3(self):
        # Ouvre le menu 3 UNE seule fois puis empile/depile chaque
        # sous-ecran a la suite (jamais un aller-retour complet par
        # l'accueil a chaque iteration) - mesure empirique : la version
        # "un _open_menu3() par sous-ecran" prenait plus de 80s pour ce
        # seul test (12 x reouverture complete depuis l'accueil).
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            for button_id in (
                "base", "limits", "security", "access-control", "aliases", "redirects", "rewrites",
                "fastcgi", "dirlisting", "cache", "error-pages", "trusted-proxy", "reverse-proxy", "auth",
            ):
                pilot.app.screen.query_one(f"#{button_id}", Button).press()
                await pilot.pause()
                pilot.app.screen.query_one("#back", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)


if __name__ == "__main__":
    unittest.main()
