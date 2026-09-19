"""Tests d'integration Phase IV de l'interface (plan interface §12,
menu 1, §3.3/§5) : registre des capacites - scan reel (pas de mock, les
sondes elles-memes n'ont pas d'effet de bord dangereux : socket.bind
best-effort, shutil.which, shutil.disk_usage, resource.getrlimit),
detail, export JSON/HTML, rafraichissement."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from textual.widgets import Button

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.capability import CapabilityStatus
from omega_serv.domain.config.option import Option
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.capabilities_screen import CapabilitiesScreen
from omega_serv.interfaces.tui.screens.capability_detail_screen import CapabilityDetailScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.widgets.capabilities_table import CapabilitiesTable

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _export_capabilities_html(capabilities, theme_name):
    from omega_serv.infrastructure.exporters.html_exporter import export_capabilities_html

    return export_capabilities_html(capabilities, theme_name)


class TestTuiCapabilities(unittest.IsolatedAsyncioTestCase):
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
        return DependencyContainer(project_root=self.root, export_capabilities_html_fn=_export_capabilities_html)

    def _generate_config(self, container: DependencyContainer) -> None:
        generate_default_config(container.configuration, container.filesystem, container.config_file)

    async def _open_capabilities(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#capabilities", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, CapabilitiesScreen)

    async def test_scan_populates_table(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            table = pilot.app.screen.query_one("#capabilities-table", CapabilitiesTable)
            self.assertEqual(table.row_count, 18)
            self.assertEqual(str(pilot.app.screen.query_one("#scan-error").content), "")

    async def test_scan_includes_fastcgi_socket_only_when_option_enabled(self):
        container = self._container()
        self._generate_config(container)
        load_result = load_config(container.configuration, container.config_file)
        assert load_result.config is not None
        new_options = dict(load_result.config.options)
        new_options["fastcgi"] = Option(name="fastcgi", enabled=True, settings={"socket_path": "var/run/php-fpm.sock"})
        container.configuration.save(container.config_file, replace(load_result.config, options=new_options))

        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            table = pilot.app.screen.query_one("#capabilities-table", CapabilitiesTable)
            self.assertEqual(table.row_count, 19)

    async def test_row_selection_opens_detail_with_matching_capability(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            table = pilot.app.screen.query_one("#capabilities-table", CapabilitiesTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, CapabilityDetailScreen)
            body = str(pilot.app.screen.query_one("#detail-body").content)
            self.assertIn("Identifiant :", body)
            self.assertIn("Statut actuel :", body)
            self.assertIn("Dernier scan :", body)

    async def test_export_json_writes_valid_payload(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            pilot.app.screen.query_one("#export-json", Button).press()
            await pilot.pause()

        export_paths = list(container.default_exports_dir.glob("capabilities-export.*.json"))
        self.assertEqual(len(export_paths), 1)
        payload = json.loads(export_paths[0].read_text())
        self.assertIn("capabilities", payload)
        self.assertEqual(len(payload["capabilities"]), 18)
        self.assertIn("status", payload["capabilities"][0])

    async def test_export_html_writes_table(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            pilot.app.screen.query_one("#export-html", Button).press()
            await pilot.pause()

        export_paths = list(container.default_exports_dir.glob("capabilities-export.*.html"))
        self.assertEqual(len(export_paths), 1)
        content = export_paths[0].read_text()
        self.assertIn("<table", content)
        self.assertIn("Registre des capacités", content)

    async def test_refresh_rescans(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            pilot.app.screen.query_one("#refresh", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#capabilities-table", CapabilitiesTable)
            self.assertEqual(table.row_count, 18)

    async def test_scan_without_config_shows_error(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            self.assertIn("Erreur", str(pilot.app.screen.query_one("#scan-error").content))
            self.assertEqual(pilot.app.screen.query_one("#capabilities-table", CapabilitiesTable).row_count, 0)

    async def test_back_button_returns_home(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(130, 50)) as pilot:
            await self._open_capabilities(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_python_version_probe_is_available(self):
        container = self._container()
        scanner = container.build_capability_scanner(8080, None)
        capabilities = scanner.scan()
        python_cap = next(c for c in capabilities if c.id == "python-version")
        self.assertEqual(python_cap.status, CapabilityStatus.AVAILABLE)


if __name__ == "__main__":
    unittest.main()
