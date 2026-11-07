"""Gestion des logs, 2026-11-07 (OMEGA-SERV_A_FAIRE_STATS_DEPUIS_OMEGA_LOG.md) : menu 5 + 5, ecran
Statistiques porte d'omega-log (calcul dans le pool de processus, exports) et Sante des logs."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textual.widgets import Button, DataTable, Input, Static

from omega_serv.__main__ import _export_payload
from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.logs.library import add_to_library
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.logs.library import LogFile
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.log_health_screen import LogHealthScreen
from omega_serv.interfaces.tui.screens.log_stats_screen import LogStatsScreen
from omega_serv.interfaces.tui.screens.logs_menu_screen import LogsMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.ports.process_runner_port import ProcessResult

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiLogStatsAndHealth(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        (self.root / "var" / "log").mkdir(parents=True)
        self.access_log = self.root / "var" / "log" / "access.log"
        self.external_log = self.root / "auth.log"

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, **kwargs) -> DependencyContainer:
        # Dossier d'unites systemd vide : jamais le vrai service omega-serv de la machine de test.
        container = DependencyContainer(project_root=self.root, export_payload_fn=_export_payload,
                                        systemd_unit_dir=self.root / "systemd", **kwargs)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        return container

    def _line(self, ip: str, hours_ago: int, status: int, path: str = "/") -> str:
        moment = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return f'{ip} - - [{moment.strftime("%d/%b/%Y:%H:%M:%S")} +0000] "GET {path} HTTP/1.1" {status} 10 "-" "curl"\n'

    async def _open(self, pilot, button_id: str) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#logs", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogsMenuScreen)
        pilot.app.screen.query_one(f"#{button_id}", Button).press()
        await pilot.pause()

    async def _wait(self, pilot, attribute: str, iterations: int = 200) -> None:
        await pilot.pause()
        for _ in range(iterations):
            if not getattr(pilot.app.screen, attribute):
                await pilot.pause()
                return
            await asyncio.sleep(0.05)
            await pilot.pause()
        self.fail("calcul jamais termine")

    async def _wait_for_file(self, pilot, pattern: str) -> list[Path]:
        for _ in range(100):
            found = list((self.root / "var" / "exports").glob(pattern))
            if found:
                return found
            await asyncio.sleep(0.05)
            await pilot.pause()
        return []

    async def test_logs_menu_has_five_buttons_per_column(self):
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "stats")
            self.assertIsInstance(pilot.app.screen, LogStatsScreen)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            menus = pilot.app.screen.query(".omega-home-menu")
            self.assertEqual([len(menu.query(Button)) for menu in menus], [5, 5])
            pilot.app.screen.query_one("#health", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogHealthScreen)

    async def test_stats_compute_shows_report_and_exports(self):
        self.access_log.write_text(
            self._line("1.1.1.1", 2, 200) + self._line("1.1.1.1", 3, 404, "/absent") + self._line("2.2.2.2", 1, 200))
        container = self._container()
        add_to_library(container.build_log_library_repository(), LogFile(path=str(self.access_log)))
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "stats")
            screen = pilot.app.screen
            screen.query_one("#selection-input", Input).value = "1"
            await pilot.pause()
            self.assertIn("1 log(s)", str(screen.query_one("#selection-size", Static).render()))
            screen.query_one("#period-Tout", Button).press()
            await self._wait(pilot, "_computing")
            summary = str(screen.query_one("#stats-summary", Static).render())
            self.assertIn("Lignes analysées   : 3", summary)
            self.assertIn("/absent", summary)
            library_table = screen.query_one("#library-table", DataTable)
            self.assertGreaterEqual(library_table.size.height, 1 + library_table.row_count)  # jamais reduite au titre
            screen.query_one("#export-json", Button).press()
            await pilot.pause()
            screen.query_one("#export-html", Button).press()
            html_files = await self._wait_for_file(pilot, "log-stats-export.*.html")
        json_files = list((self.root / "var" / "exports").glob("log-stats-export.*.json"))
        self.assertEqual(len(json_files), 1)
        data = json.loads(json_files[0].read_text())
        self.assertEqual(data["report"]["total"], 3)
        self.assertEqual(len(html_files), 1)
        self.assertIn("/absent", html_files[0].read_text())

    async def test_stats_without_selection_says_so(self):
        app = OmegaServApp(self._container())
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "stats")
            pilot.app.screen.query_one("#period-24h", Button).press()
            await pilot.pause()
            self.assertIn("Saisissez", str(pilot.app.screen.query_one("#stats-error", Static).render()))
            self.assertFalse(pilot.app.screen._computing)

    async def test_health_lists_logs_and_exports_three_formats(self):
        self.access_log.write_text(self._line("1.1.1.1", 2, 200))
        container = self._container()
        add_to_library(container.build_log_library_repository(), LogFile(path=str(self.external_log)))
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "health")
            screen = pilot.app.screen
            await self._wait(pilot, "_analysing")
            table = screen.query_one("#health-table", DataTable)
            self.assertEqual(table.row_count, 6)  # 5 logs d'omega-serv + 1 de la Bibliotheque
            self.assertGreater(table.size.height, 2)
            self.assertIn("Résumé", str(screen.query_one("#health-summary", Static).render()))
            table.move_cursor(row=5)
            await pilot.pause()
            self.assertIn("Fichier absent", str(screen.query_one("#health-detail", Static).render()))
            screen.query_one("#export-json", Button).press()
            await pilot.pause()
            screen.query_one("#export-html", Button).press()
            html_files = await self._wait_for_file(pilot, "log-health-export.*.html")
            screen.query_one("#export-txt", Button).press()
            txt_files = await self._wait_for_file(pilot, "log-health-export.*.txt")
        data = json.loads(next((self.root / "var" / "exports").glob("log-health-export.*.json")).read_text())
        library = [log for log in data["logs"] if log["origin"] == "library"]
        self.assertEqual(library[0]["findings"][0]["code"], "missing_library")
        self.assertEqual(data["counts"]["problem"], 1, [(log["path"], log["findings"]) for log in data["logs"]])
        self.assertIn(str(self.external_log), html_files[0].read_text())
        self.assertIn("Santé des logs", txt_files[0].read_text())

    async def test_health_fix_with_sudo_shows_and_runs_the_exact_command(self):
        self.external_log.write_text(self._line("1.1.1.1", 1, 200))
        self.external_log.chmod(0o666)
        calls: list[list[str]] = []

        class FakeSudo:
            def run_interactive(self, args):
                calls.append(args)
                return 0

            def run(self, args, input_text=None, timeout=None):
                calls.append(args)
                if "o-w" in args:
                    os.chmod(args[-1], 0o644)
                return ProcessResult(0, "", "")

        container = self._container(privileged_runner_factory=FakeSudo)
        add_to_library(container.build_log_library_repository(), LogFile(path=str(self.external_log)))
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "health")
            screen = pilot.app.screen
            await self._wait(pilot, "_analysing")
            screen.query_one("#health-table", DataTable).move_cursor(row=5)
            await pilot.pause()
            self.assertFalse(screen.query_one("#fix-sudo", Button).disabled)
            screen.query_one("#fix-sudo", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertIn(f"sudo chmod o-w {self.external_log}", " ".join(str(w.render()) for w in pilot.app.screen.query(Static)))
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._wait(pilot, "_analysing")
        self.assertIn(["sudo", "-v"], calls)
        self.assertIn(["sudo", "-n", "chmod", "o-w", "--", str(self.external_log)], calls)
        self.assertEqual(self.external_log.stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
