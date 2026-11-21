# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Rapport complet (projets 3.0.0 §7.7 et §7.10) : sommaire a l'ecran, exports HTML/TXT/JSON sans secret, detail
seulement si coche. Projet temporaire, dossier d'export temporaire."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Checkbox, Select, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.report.full_report import scrub
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.full_report_screen import FullReportScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestScrub(unittest.TestCase):
    def test_secrets_become_defined_or_absent(self):
        data = {"users": [{"name": "a", "password_hash": "scrypt$x"}], "api_token": "", "zones": ["/a/"]}
        self.assertEqual(scrub(data), {"users": [{"name": "a", "password_hash": True}], "api_token": False,
                                       "zones": ["/a/"]})


class TestTuiFullReport(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.exports = self.root / "exports"
        self.container = self._container()
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)
        self.container.settings_store.set("exports_dir_override", str(self.exports))

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self) -> DependencyContainer:
        from omega_serv.__main__ import (
            _export_payload,  # rendu HTML branche comme au lancement reel
        )

        return DependencyContainer(project_root=self.root, instance_registry_path=self.root / "registre.json",
                                   systemd_unit_dir=self.root / "unites", export_payload_fn=_export_payload)

    async def _wait_idle(self, pilot) -> None:
        for _ in range(200):
            await pilot.pause(0.05)
            if not pilot.app.screen.query_one("#report-summary", Static).loading:
                return

    def test_reverse_proxy_option_present_does_not_break_the_report(self):
        """Regression 2026-11-18 : la liste des zones etait lue sur tout le dictionnaire de l'option (« string
        indices must be integers ») des que `reverse_proxy` figurait dans la configuration, meme desactivee."""
        from omega_serv.application.config.load_config import load_config

        path = self.container.config_file
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("options", {})["reverse_proxy"] = {"enabled": False, "cache_max_size_mb": 100}
        path.write_text(json.dumps(data), encoding="utf-8")
        result = load_config(self.container.configuration, path)
        self.assertTrue(result.success, result.errors)
        report = self.container.collect_full_report(result.config)
        self.assertIn("listen", report)

    async def test_summary_then_exports(self):
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.press("x")
            await pilot.pause()
            if isinstance(pilot.app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
                await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)
            pilot.app.screen.query_one("#report", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, FullReportScreen)
            await self._wait_idle(pilot)
            summary = str(pilot.app.screen.query_one("#report-summary", Static).content)
            for expected in ("Identité", "Uptime", "Mode", "Moteur utilisé", "TLS", "Options", "Sauvegardes"):
                self.assertIn(expected, summary)
            for export in ("json", "txt", "html"):
                pilot.app.screen.query_one("#export-format", Select).value = export
                if export == "json":
                    pilot.app.screen.query_one("#detail-zones", Checkbox).value = True
                pilot.app.screen.query_one("#export", Button).press()
                await self._wait_idle(pilot)
                for _ in range(40):
                    if list(self.exports.glob(f"omega-serv-rapport.*.{export}")):
                        break
                    await pilot.pause(0.05)
        payload = json.loads(next(self.exports.glob("omega-serv-rapport.*.json")).read_text())
        self.assertEqual(payload["listen"]["mode"], "web")
        self.assertIn("zones", payload["details"])
        self.assertIn("RAPPORT COMPLET", next(self.exports.glob("omega-serv-rapport.*.txt")).read_text())
        html = next(self.exports.glob("omega-serv-rapport.*.html")).read_text()
        self.assertIn("<html", html)
        self.assertIn("Sauvegardes", html)


if __name__ == "__main__":
    unittest.main()
