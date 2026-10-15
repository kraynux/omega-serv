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
from dataclasses import replace
from pathlib import Path

from textual.widgets import Button, DataTable, Input, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import Option
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.config_check_screen import ConfigCheckScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.csp_zone_wizard_screen import CspZoneWizardScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.options_screen import OptionsScreen
from omega_serv.interfaces.tui.screens.reverse_proxy_cache_screen import ReverseProxyCacheScreen
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

    def _seed_alias(self, container: DependencyContainer, *, url_prefix: str) -> None:
        load_result = load_config(container.configuration, container.config_file)
        assert load_result.config is not None
        new_options = dict(load_result.config.options)
        new_options["aliases"] = Option(
            name="aliases", enabled=True,
            settings={"list": [{"url_prefix": url_prefix, "target_path": "webroot/media", "allow_outside_webroot": False}]},
        )
        container.configuration.save(container.config_file, replace(load_result.config, options=new_options))

    def _enable_reverse_proxy(self, container: DependencyContainer) -> None:
        # `detect_zone_prefix_overlaps` n'inclut une zone que si son option est `enabled`
        # (domain/config/rules.py::_collect_dispatch_zone_prefixes) - jamais active via le
        # seul CRUD de zones (`reverse_proxy_screen.py` preserve `existing.enabled`).
        load_result = load_config(container.configuration, container.config_file)
        assert load_result.config is not None
        existing = load_result.config.options.get("reverse_proxy")
        new_settings = dict(existing.settings) if existing is not None else {"zones": []}
        new_options = dict(load_result.config.options)
        new_options["reverse_proxy"] = Option(name="reverse_proxy", enabled=True, settings=new_settings)
        container.configuration.save(container.config_file, replace(load_result.config, options=new_options))

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
            pilot.app.screen.query_one("#coep-mode-input", Input).value = "require-corp"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
        config_text = container.config_file.read_text()
        self.assertIn('"csp_mode": "report-only"', config_text)
        self.assertIn('"coep_mode": "require-corp"', config_text)

    async def test_security_screen_csp_zone_add_and_delete(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#security", Button).press()
            await pilot.pause()

            pilot.app.screen.query_one("#add-zone", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, CspZoneWizardScreen)
            pilot.app.screen.query_one("#wiz-path-prefix", Input).value = "/public-widgets/"
            # Pre-rempli avec "'self'" (politique globale) - on y ajoute unsafe-inline.
            self.assertEqual(pilot.app.screen.query_one("#wiz-style-src", Input).value, "'self'")
            pilot.app.screen.query_one("#wiz-style-src", Input).value = "'self' 'unsafe-inline'"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#csp-zones-table", DataTable).row_count, 1)
            config_text = container.config_file.read_text()
            self.assertIn('"path_prefix": "/public-widgets/"', config_text)
            self.assertIn("unsafe-inline", config_text)

            table = pilot.app.screen.query_one("#csp-zones-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-zone", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#csp-zones-table", DataTable).row_count, 0)

    async def test_csp_zone_wizard_prefills_every_directive_with_the_current_global_policy(self):
        """Retour utilisateur 2026-10-10 : jamais un champ vide qui
        inviterait a sacrifier des directives sans le vouloir."""
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#security", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-zone", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#wiz-default-src", Input).value, "'none'")
            self.assertEqual(pilot.app.screen.query_one("#wiz-object-src", Input).value, "'none'")
            self.assertEqual(pilot.app.screen.query_one("#wiz-script-src", Input).value, "'self'")

    async def test_csp_zone_wizard_cancel_adds_nothing(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#security", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#csp-zones-table", DataTable).row_count, 0)

    async def test_csp_zone_without_risky_directive_skips_the_extra_confirmation(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#security", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#wiz-path-prefix", Input).value = "/strict-zone/"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#csp-zones-table", DataTable).row_count, 1)

    async def test_security_screen_rejects_invalid_coep_mode(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#security", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#coep-mode-input", Input).value = "strict"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("coep_mode", str(pilot.app.screen.query_one("#form-error").content))

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

    async def _add_upstream_in_editor(
        self, pilot, *, host: str, port: str, use_tls: str = "non", weight: str = "1",
        load_source: str = "none", load_check_path: str = "/", max_concurrent_requests: str = "",
        active_health_check_enabled: str = "non", active_health_check_path: str = "/",
    ) -> None:
        pilot.app.screen.query_one("#add", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#df-host", Input).value = host
        pilot.app.screen.query_one("#df-port", Input).value = port
        pilot.app.screen.query_one("#df-use_tls", Input).value = use_tls
        pilot.app.screen.query_one("#df-weight", Input).value = weight
        pilot.app.screen.query_one("#df-load_source", Input).value = load_source
        pilot.app.screen.query_one("#df-load_check_path", Input).value = load_check_path
        pilot.app.screen.query_one("#df-max_concurrent_requests", Input).value = max_concurrent_requests
        pilot.app.screen.query_one("#df-active_health_check_enabled", Input).value = active_health_check_enabled
        pilot.app.screen.query_one("#df-active_health_check_path", Input).value = active_health_check_path
        pilot.app.screen.query_one("#confirm", Button).press()
        await pilot.pause()

    async def test_reverse_proxy_save_persists_backpressure_and_active_health_fields(self):
        """Regression : `max_concurrent_requests` (Phase 7bis) n'etait
        PAS serialise par `_save_zones` (capture correctement par
        `UpstreamEditorScreen` mais silencieusement perdu a l'ecriture
        disque - trouve en cablant le controle actif, §18.2) - verifie
        ici un vrai aller-retour complet (saisie TUI -> ecriture disque
        -> reparse) pour les deux, jamais seulement l'etat en memoire du
        formulaire intermediaire."""
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
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(
                pilot, host="127.0.0.1", port="3000", max_concurrent_requests="7",
                active_health_check_enabled="oui", active_health_check_path="/healthz",
            )
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
            await pilot.pause()

        reloaded = self._container()
        load_result = load_config(reloaded.configuration, reloaded.config_file)
        assert load_result.config is not None
        zones = load_result.config.options["reverse_proxy"].settings["zones"]
        upstream = zones[0]["upstreams"][0]
        self.assertEqual(upstream["max_concurrent_requests"], 7)
        self.assertTrue(upstream["active_health_check_enabled"])
        self.assertEqual(upstream["active_health_check_path"], "/healthz")

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
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3000")
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
            await pilot.pause()
            table = pilot.app.screen.query_one("#proxy-zones-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(
                list(table.get_row_at(0)), ["/api/", "round_robin", "127.0.0.1:3000", "Non", "Oui", "Non", "Non"],
            )

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#edit", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-preserve_host_header", Input).value = "oui"
            pilot.app.screen.query_one("#df-verify_upstream_tls", Input).value = "non"
            pilot.app.screen.query_one("#df-websocket_enabled", Input).value = "oui"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            # Ecran d'edition des backends : le backend existant est deja liste, on en ajoute un second.
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="4001", use_tls="oui", weight="2")
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
            await pilot.pause()
            config_text = container.config_file.read_text()
            self.assertIn('"port": 4001', config_text)
            self.assertIn('"use_tls": true', config_text)
            self.assertIn('"weight": 2', config_text)
            self.assertIn('"verify_upstream_tls": false', config_text)
            self.assertIn('"websocket_enabled": true', config_text)
            self.assertEqual(
                list(table.get_row_at(0)),
                ["/api/", "round_robin", "127.0.0.1:3000, https://127.0.0.1:4001 (poids 2)", "Oui", "Non", "Oui", "Non"],
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
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="99999")
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
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
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-host", Input).value = "127.0.0.1"
            pilot.app.screen.query_one("#df-port", Input).value = "not-a-number"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("nombres entiers", str(pilot.app.screen.query_one("#upstream-error").content))
            # Le backend invalide n'a pas ete ajoute a la liste - valider sans aucun backend
            # doit etre rejete par validate_proxy_zone (point unique de validation).
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
            await pilot.pause()
            self.assertIn("au moins un upstream est requis", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#proxy-zones-table", DataTable).row_count, 0)

    async def test_reverse_proxy_rejects_invalid_load_balancing(self):
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
            pilot.app.screen.query_one("#df-load_balancing", Input).value = "lottery"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3000")
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
            await pilot.pause()
            self.assertIn("load_balancing invalide", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#proxy-zones-table", DataTable).row_count, 0)

    async def test_reverse_proxy_sticky_session_and_routing_rule_round_trip(self):
        """§17 : champs d'affinite de session (etape 1) + une regle de
        routage sur en-tete reellement ajoutee (etape 3, nouvel ecran
        `RoutingRuleEditorScreen`) - bout en bout jusqu'a la config JSON."""
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
            pilot.app.screen.query_one("#df-sticky_session_enabled", Input).value = "oui"
            pilot.app.screen.query_one("#df-sticky_cookie_name", Input).value = "mon_cookie"
            pilot.app.screen.query_one("#df-sticky_cookie_max_age_seconds", Input).value = "600"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3000")
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3001")
            pilot.app.screen.query_one("#confirm", Button).press()  # Valider UpstreamEditorScreen
            await pilot.pause()
            # RoutingRuleEditorScreen : ajouter une regle ciblant le 2e backend.
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-header_name", Input).value = "X-Canary"
            pilot.app.screen.query_one("#df-pattern", Input).value = "true"
            pilot.app.screen.query_one("#df-upstream_key", Input).value = "127.0.0.1:3001"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # Valider RoutingRuleEditorScreen
            await pilot.pause()

            table = pilot.app.screen.query_one("#proxy-zones-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(list(table.get_row_at(0))[-1], "Oui")  # colonne Sticky

            config_text = container.config_file.read_text()
            self.assertIn('"sticky_session_enabled": true', config_text)
            self.assertIn('"sticky_cookie_name": "mon_cookie"', config_text)
            self.assertIn('"sticky_cookie_max_age_seconds": 600', config_text)
            self.assertIn('"header_name": "X-Canary"', config_text)
            self.assertIn('"upstream_key": "127.0.0.1:3001"', config_text)

    async def test_reverse_proxy_rejects_unknown_upstream_key_in_routing_rule(self):
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
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3000")
            pilot.app.screen.query_one("#confirm", Button).press()  # Valider UpstreamEditorScreen
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-header_name", Input).value = "X-Canary"
            pilot.app.screen.query_one("#df-pattern", Input).value = "true"
            pilot.app.screen.query_one("#df-upstream_key", Input).value = "10.0.0.99:9999"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # Valider RoutingRuleEditorScreen
            await pilot.pause()
            self.assertIn("upstream_key", str(pilot.app.screen.query_one("#form-error").content))
            self.assertIn("inconnu", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#proxy-zones-table", DataTable).row_count, 0)

    async def test_reverse_proxy_real_load_round_trip(self):
        """Phase 7 (§19) : strategie real_load + un backend natif et un
        backend declaratif dans la MEME zone (granularite par upstream,
        §19.3), jusqu'a la config JSON."""
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
            pilot.app.screen.query_one("#df-load_balancing", Input).value = "real_load"
            pilot.app.screen.query_one("#df-load_poll_interval_seconds", Input).value = "5"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3000", load_source="native")
            await self._add_upstream_in_editor(
                pilot, host="127.0.0.1", port="3001", load_source="declarative", load_check_path="/ma-sonde",
            )
            pilot.app.screen.query_one("#confirm", Button).press()  # Valider UpstreamEditorScreen
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # Valider RoutingRuleEditorScreen, aucune regle
            await pilot.pause()

            table = pilot.app.screen.query_one("#proxy-zones-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(list(table.get_row_at(0))[1], "real_load")

            config_text = container.config_file.read_text()
            self.assertIn('"load_balancing": "real_load"', config_text)
            self.assertIn('"load_poll_interval_seconds": 5.0', config_text)
            self.assertIn('"load_source": "native"', config_text)
            self.assertIn('"load_source": "declarative"', config_text)
            self.assertIn('"load_check_path": "/ma-sonde"', config_text)

    async def test_reverse_proxy_cache_screen_stats_purge_and_max_size_round_trip(self):
        """Phase 8 (§21) : l'ecran dedie lit reellement le disque
        (var/cache/reverse_proxy/), purge reellement les fichiers, et
        modifie reellement `cache_max_size_mb` dans la config JSON."""
        container = self._container()
        self._generate_config(container)
        cache_dir = container.project_root / "var" / "cache" / "reverse_proxy" / "api"
        cache_dir.mkdir(parents=True)
        (cache_dir / "entry1.json").write_text("{}")
        (cache_dir / "entry2.json").write_text("{}")

        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#reverse-proxy-cache", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ReverseProxyCacheScreen)
            stats_text = str(pilot.app.screen.query_one("#cache-stats", Static).content)
            self.assertIn("2 entree", stats_text)

            # Modifier le plafond de taille global.
            pilot.app.screen.query_one("#edit-max-size", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cache_max_size_mb", Input).value = "250"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("250 Mo", str(pilot.app.screen.query_one("#cache-stats", Static).content))
            config_text = container.config_file.read_text()
            self.assertIn('"cache_max_size_mb": 250', config_text)

            # Purger une zone precise.
            pilot.app.screen.query_one("#purge-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-zone_prefix", Input).value = "/api/"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # ConfirmScreen
            await pilot.pause()
            self.assertIn("0 entree", str(pilot.app.screen.query_one("#cache-stats", Static).content))
            self.assertFalse(any(cache_dir.glob("*.json")))

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
        """Regression 2026-09-29 (retour utilisateur : suppression/
        changement de mot de passe exigeaient de retaper de memoire un
        champ vide - deux DataTable avec selection desormais, meme
        patron que les autres ecrans CRUD, voir INFO DEV)."""
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
            users_table = pilot.app.screen.query_one("#users-table", DataTable)
            self.assertEqual(users_table.row_count, 1)

            pilot.app.screen.query_one("#check-permissions", Button).press()
            await pilot.pause()
            self.assertIn("0o640", str(pilot.app.screen.query_one("#form-error").content))

            pilot.app.screen.query_one("#create-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-path_prefix", Input).value = "/admin/"
            pilot.app.screen.query_one("#df-realm", Input).value = "Admin"
            pilot.app.screen.query_one("#df-allowed_users", Input).value = "alice"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            zones_table = pilot.app.screen.query_one("#zones-table", DataTable)
            self.assertEqual(zones_table.row_count, 1)

            # Changer le mot de passe : selection dans la table, aucun champ
            # nom d'utilisateur a remplir (deja connu de la selection).
            users_table.move_cursor(row=0)
            users_table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#change-password", Button).press()
            await pilot.pause()
            self.assertEqual(len(pilot.app.screen.query("#df-username")), 0)
            pilot.app.screen.query_one("#df-password", Input).value = "newsecretpass"
            pilot.app.screen.query_one("#df-password_confirm", Input).value = "newsecretpass"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#users-table", DataTable).row_count, 1)

            # Suppression : selection dans la table, confirmation directe,
            # aucun formulaire intermediaire.
            users_table.move_cursor(row=0)
            users_table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#remove-user", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#users-table", DataTable).row_count, 0)

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
            self.assertEqual(pilot.app.screen.query_one("#users-table", DataTable).row_count, 0)

    async def test_back_buttons_return_to_menu3(self):
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


    async def test_reverse_proxy_save_warns_on_prefix_overlap_with_alias(self):
        container = self._container()
        self._generate_config(container)
        self._seed_alias(container, url_prefix="/api/")
        self._enable_reverse_proxy(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#reverse-proxy", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/api/"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3000")
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(
                any("chevauchement" in m and "options.alias" in m and "options.reverse_proxy" in m for m in messages),
                messages,
            )

    async def test_reverse_proxy_save_without_overlap_warns_nothing(self):
        container = self._container()
        self._generate_config(container)
        self._seed_alias(container, url_prefix="/media/")
        self._enable_reverse_proxy(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_menu3(pilot)
            pilot.app.screen.query_one("#reverse-proxy", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-url_prefix", Input).value = "/api/"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._add_upstream_in_editor(pilot, host="127.0.0.1", port="3000")
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()  # RoutingRuleEditorScreen, aucune regle
            await pilot.pause()
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertFalse(any("chevauchement" in m for m in messages), messages)


if __name__ == "__main__":
    unittest.main()
