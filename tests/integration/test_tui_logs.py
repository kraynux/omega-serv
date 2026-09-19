"""Tests d'integration Phase V/VI de l'interface (plan interface §12,
menu 4) : voir/suivre un fichier log, ecran lnav (double simple pour
container.lnav_runner - jamais le vrai rendu PTY+pyte, qui exige un
terminal reel, voir tests/unit/test_lnav_pty_session.py et
test_lnav_live_renderer.py pour les parties reellement testables sans
terminal interactif), rotation/archivage, restaurer/purger une archive,
export de la liste des archives, statistiques et top IPs (Phase VI)."""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textual.widgets import Button, Checkbox, DataTable, RichLog, Select

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.export_log_archives_screen import ExportLogArchivesScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.lnav_screen import LnavScreen
from omega_serv.interfaces.tui.screens.log_rotation_screen import LogRotationScreen
from omega_serv.interfaces.tui.screens.log_stats_screen import LogStatsScreen
from omega_serv.interfaces.tui.screens.log_viewer_screen import LogViewerScreen
from omega_serv.interfaces.tui.screens.logs_menu_screen import LogsMenuScreen
from omega_serv.interfaces.tui.screens.purge_log_archives_screen import PurgeLogArchivesScreen
from omega_serv.interfaces.tui.screens.restore_log_archive_screen import RestoreLogArchiveScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.screens.top_ips_screen import TopIpsScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _export_log_archives_html(archives, theme_name):
    from omega_serv.infrastructure.exporters.html_exporter import export_log_archives_html

    return export_log_archives_html(archives, theme_name)


class TestTuiLogs(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        (self.root / "var" / "log").mkdir(parents=True)
        self.access_log = self.root / "var" / "log" / "access.log"
        self.lnav_calls: list[tuple] = []

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_lnav_runner(self, paths, palette, title, menu_label):
        self.lnav_calls.append((paths, title, menu_label))

    def _container(self, **kwargs) -> DependencyContainer:
        return DependencyContainer(project_root=self.root, **kwargs)

    def _generate_config(self, container: DependencyContainer) -> None:
        generate_default_config(container.configuration, container.filesystem, container.config_file)

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_logs_menu(self, pilot) -> None:
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#logs", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_viewer_shows_missing_file_message(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#viewer", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogViewerScreen)
            pilot.app.screen.query_one("#open-access", Button).press()
            await pilot.pause()
            log_widget = pilot.app.screen.query_one("#log-content", RichLog)
            self.assertEqual(len(log_widget.lines), 1)

    async def test_viewer_shows_existing_lines_and_follows_new_ones(self):
        self.access_log.write_text("line1\nline2\n")
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#viewer", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#open-access", Button).press()
            await pilot.pause()
            log_widget = pilot.app.screen.query_one("#log-content", RichLog)
            self.assertEqual(len(log_widget.lines), 2)

            pilot.app.screen.query_one("#follow", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#follow", Button).label), "Arreter le suivi")

            with self.access_log.open("a", encoding="utf-8") as f:
                f.write("line3\n")
            await asyncio.sleep(1.3)
            await pilot.pause()
            self.assertEqual(len(log_widget.lines), 3)

            pilot.app.screen.query_one("#follow", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#follow", Button).label), "Suivre en direct")

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions - test non pertinent")
    async def test_viewer_shows_a_clean_error_instead_of_crashing_on_permission_denied(self):
        """Retour utilisateur 2026-09-14 : "j'ai clique sur waf-alerts.log,
        ca a bloque l'application" - un fichier de var/log/ peut
        appartenir au compte systeme dedie du service pendant que la
        session TUI courante n'a pas encore pris en compte l'appartenance
        de groupe qui donnerait normalement l'acces (meme cause deja
        rencontree et corrigee pour Active Defense, jamais protegee ici
        avant ce correctif). Vrai fichier reellement illisible (jamais
        un mock), meme discipline que test_sqlite_active_defense_
        connection.py::TestOpenActiveDefenseConnectionPermissionError."""
        self.access_log.write_text("line1\n")
        self.access_log.chmod(0o000)
        try:
            container = self._container()
            self._generate_config(container)
            app = OmegaServApp(container)
            async with app.run_test(size=(120, 45)) as pilot:
                await self._start(pilot)
                await self._open_logs_menu(pilot)
                pilot.app.screen.query_one("#viewer", Button).press()
                await pilot.pause()
                pilot.app.screen.query_one("#open-access", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, LogViewerScreen)
                log_widget = pilot.app.screen.query_one("#log-content", RichLog)
                content = "\n".join(str(line) for line in log_widget.lines)
                self.assertIn("impossible de lire", content)
        finally:
            self.access_log.chmod(0o644)

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions - test non pertinent")
    async def test_viewer_follow_stops_cleanly_if_file_becomes_unreadable(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        try:
            async with app.run_test(size=(120, 45)) as pilot:
                await self._start(pilot)
                await self._open_logs_menu(pilot)
                pilot.app.screen.query_one("#viewer", Button).press()
                await pilot.pause()
                pilot.app.screen.query_one("#open-access", Button).press()
                await pilot.pause()
                pilot.app.screen.query_one("#follow", Button).press()
                await pilot.pause()
                self.assertEqual(str(pilot.app.screen.query_one("#follow", Button).label), "Arreter le suivi")

                with self.access_log.open("a", encoding="utf-8") as f:
                    f.write("line2\n")
                self.access_log.chmod(0o000)
                await asyncio.sleep(1.3)
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, LogViewerScreen)
                self.assertEqual(str(pilot.app.screen.query_one("#follow", Button).label), "Suivre en direct")
                log_widget = pilot.app.screen.query_one("#log-content", RichLog)
                content = "\n".join(str(line) for line in log_widget.lines)
                self.assertIn("suivi interrompu", content)
        finally:
            self.access_log.chmod(0o644)

    async def test_viewer_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#viewer", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_lnav_launches_with_selected_known_log(self):
        self.access_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#lnav", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LnavScreen)
            pilot.app.screen.query_one("#check-access", Checkbox).value = True
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertEqual(len(self.lnav_calls), 1)
            paths, _title, _menu_label = self.lnav_calls[0]
            self.assertEqual(paths, (self.access_log,))
            self.assertEqual(str(pilot.app.screen.query_one("#lnav-error").content), "")

    async def test_lnav_refuses_when_all_selected_files_are_missing(self):
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#check-error", Checkbox).value = True
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIn("Aucun fichier valide", str(pilot.app.screen.query_one("#lnav-error").content))
            self.assertEqual(len(self.lnav_calls), 0)

    async def test_lnav_launches_with_partial_selection_when_one_file_missing(self):
        self.access_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#check-access", Checkbox).value = True
            pilot.app.screen.query_one("#check-error", Checkbox).value = True
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertEqual(len(self.lnav_calls), 1)
            paths, _title, _menu_label = self.lnav_calls[0]
            self.assertEqual(paths, (self.access_log,))

    async def test_lnav_unavailable_without_injected_runner(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#check-access", Checkbox).value = True
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIn("indisponible", str(pilot.app.screen.query_one("#lnav-error").content))

    async def test_lnav_back_button_returns_to_logs_menu(self):
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_logs_menu_back_button_returns_home(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)


    def _archive_line(self, ip: str, hours_ago: int, status: int) -> str:
        timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return f'{ip} - - [{timestamp.strftime("%d/%b/%Y:%H:%M:%S")} +0000] "GET / HTTP/1.1" {status} 10 "-" "curl"\n'

    def _archives_dir(self, container: DependencyContainer) -> Path:
        return container.project_root / "var" / "backups" / "logs"

    async def test_rotation_reports_not_needed_below_threshold(self):
        self.access_log.write_text("small")
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#rotation", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogRotationScreen)
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIn("non necessaire", str(pilot.app.screen.query_one("#rotation-result").content))

    async def test_backup_now_rotates_unconditionally(self):
        self.access_log.write_text("small")
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#rotation", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#mode-select", Select).value = "backup"
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIn("Log tourne", str(pilot.app.screen.query_one("#rotation-result").content))
        archives = list((self._archives_dir(container)).glob("access.log.*.tar.gz"))
        self.assertEqual(len(archives), 1)

    async def test_configure_schedule_then_manage_and_delete(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#rotation", Button).press()
            await pilot.pause()

            pilot.app.screen.query_one("#mode-select", Select).value = "schedule"
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIn("Automatisation enregistree", str(pilot.app.screen.query_one("#rotation-result").content))

            pilot.app.screen.query_one("#mode-select", Select).value = "manage"
            await pilot.pause()
            table = pilot.app.screen.query_one("#automations-table", DataTable)
            self.assertEqual(table.row_count, 1)

            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-automation", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#automations-table", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_rotation_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#rotation", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_restore_lists_and_restores_selected_archive(self):
        self.access_log.write_text("line1\nline2\n")
        container = self._container()
        self._generate_config(container)
        container.rotate_log_if_needed(self.access_log, max_size_bytes=1, keep=3, archive_base_dir=self._archives_dir(container))
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#restore", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, RestoreLogArchiveScreen)
            table = pilot.app.screen.query_one("#archives-table", DataTable)
            self.assertEqual(table.row_count, 1)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#restore", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#restore-error").content), "")
            restored_dirs = list((container.project_root / "var" / "log" / "restored").iterdir())
            self.assertEqual(len(restored_dirs), 1)
            self.assertEqual((restored_dirs[0] / "access.log").read_text(), "line1\nline2\n")

    async def test_restore_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#restore", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_purge_requires_confirmation_before_deleting(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        container.rotate_log_if_needed(self.access_log, max_size_bytes=1, keep=3, archive_base_dir=self._archives_dir(container))
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#purge", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, PurgeLogArchivesScreen)
            table = pilot.app.screen.query_one("#archives-table", DataTable)
            self.assertEqual(table.row_count, 1)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#purge", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, PurgeLogArchivesScreen)
            table = pilot.app.screen.query_one("#archives-table", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_purge_cancelled_keeps_archive(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        container.rotate_log_if_needed(self.access_log, max_size_bytes=1, keep=3, archive_base_dir=self._archives_dir(container))
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#purge", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#archives-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#purge", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#archives-table", DataTable)
            self.assertEqual(table.row_count, 1)

    async def test_purge_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#purge", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_export_writes_json_and_html(self):
        self.access_log.write_text("line1\n")
        container = self._container(export_log_archives_html_fn=_export_log_archives_html)
        self._generate_config(container)
        container.rotate_log_if_needed(self.access_log, max_size_bytes=1, keep=3, archive_base_dir=self._archives_dir(container))
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#export", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ExportLogArchivesScreen)
            table = pilot.app.screen.query_one("#archives-table", DataTable)
            self.assertEqual(table.row_count, 1)
            pilot.app.screen.query_one("#export-json", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#export-html", Button).press()
            await pilot.pause()
        self.assertEqual(len(list(container.default_exports_dir.glob("log-archives-export.*.json"))), 1)
        self.assertEqual(len(list(container.default_exports_dir.glob("log-archives-export.*.html"))), 1)

    async def test_export_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#export", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_stats_shows_totals_for_selected_period(self):
        self.access_log.write_text(self._archive_line("1.1.1.1", 3, 200) + self._archive_line("2.2.2.2", 2, 404))
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#stats", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogStatsScreen)
            pilot.app.screen.query_one("#period-7d", Button).press()
            await pilot.pause()
            summary_text = str(pilot.app.screen.query_one("#stats-summary").content)
            self.assertIn("Total requetes : 2", summary_text)
            self.assertIn("404", summary_text)
            self.assertIn("1.1.1.1", summary_text)

    async def test_stats_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#stats", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    async def test_top_ips_lists_and_removes_selected_ip(self):
        self.access_log.write_text(self._archive_line("1.1.1.1", 2, 200) + self._archive_line("2.2.2.2", 1, 200))
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#top-ips", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TopIpsScreen)
            table = pilot.app.screen.query_one("#top-ips-table", DataTable)
            self.assertEqual(table.row_count, 2)
            table.move_cursor(row=0)
            await pilot.pause()
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#remove-ip", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TopIpsScreen)
            table = pilot.app.screen.query_one("#top-ips-table", DataTable)
            self.assertEqual(table.row_count, 1)
        self.assertNotIn("1.1.1.1", self.access_log.read_text())
        self.assertIn("2.2.2.2", self.access_log.read_text())

    async def test_top_ips_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_logs_menu(pilot)
            pilot.app.screen.query_one("#top-ips", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)


if __name__ == "__main__":
    unittest.main()
