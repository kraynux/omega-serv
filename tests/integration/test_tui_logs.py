"""Tests d'integration de l'interface "Gestion des logs" - refonte menu
2026-10-15 (deux colonnes BIBLIOTHEQUE/MAINTENANCE, au meme niveau
qu'omega-log) : Bibliotheque, Favoris, Voir les logs (3 viewers :
Simple/Classique/lnav), Voir et traiter IP, rotation/archivage,
restaurer/purger une archive, export de la liste des archives. lnav lui
meme garde un double simple pour container.lnav_runner (jamais le vrai
rendu PTY+pyte, qui exige un terminal reel, voir
tests/unit/test_lnav_pty_session.py et test_lnav_live_renderer.py)."""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textual.css.query import NoMatches
from textual.widgets import Button, Checkbox, DataTable, Input, RichLog, Select, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.logs.library import add_to_library
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import Option
from omega_serv.domain.logs.library import LogFile
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.export_log_archives_screen import ExportLogArchivesScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.lnav_screen import LnavScreen
from omega_serv.interfaces.tui.screens.log_favorites_screen import LogFavoritesScreen
from omega_serv.interfaces.tui.screens.log_library_screen import LogLibraryScreen
from omega_serv.interfaces.tui.screens.log_rotation_screen import LogRotationScreen
from omega_serv.interfaces.tui.screens.log_simple_viewer_screen import LogSimpleViewerScreen
from omega_serv.interfaces.tui.screens.log_view_screen import LogViewScreen
from omega_serv.interfaces.tui.screens.log_viewer_screen import LogViewerScreen
from omega_serv.interfaces.tui.screens.logs_menu_screen import LogsMenuScreen
from omega_serv.interfaces.tui.screens.process_ip_screen import ProcessIpScreen
from omega_serv.interfaces.tui.screens.purge_log_archives_screen import PurgeLogArchivesScreen
from omega_serv.interfaces.tui.screens.restore_log_archive_screen import RestoreLogArchiveScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

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

    def _add_to_library(self, container: DependencyContainer, path: Path, *, access: str = "file") -> None:
        add_to_library(container.build_log_library_repository(), LogFile(path=str(path), access=access))

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

    async def _open_library(self, pilot) -> None:
        await self._open_logs_menu(pilot)
        pilot.app.screen.query_one("#library", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogLibraryScreen)

    async def _open_favorites(self, pilot) -> None:
        await self._open_logs_menu(pilot)
        pilot.app.screen.query_one("#favorites", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogFavoritesScreen)

    async def _open_view_logs(self, pilot) -> None:
        await self._open_logs_menu(pilot)
        pilot.app.screen.query_one("#view-logs", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogViewScreen)

    async def _open_process_ip(self, pilot) -> None:
        await self._open_logs_menu(pilot)
        pilot.app.screen.query_one("#process-ip", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ProcessIpScreen)

    def _enable_waf_magnet(self, container: DependencyContainer) -> None:
        load_result = load_config(container.configuration, container.config_file)
        assert load_result.config is not None
        new_options = dict(load_result.config.options)
        new_options["waf"] = Option(name="waf", enabled=True, settings={"magnet": {"enabled": True}})
        new_config = replace(load_result.config, options=new_options)
        container.configuration.save(container.config_file, new_config)

    def _archive_line(self, ip: str, hours_ago: int, status: int) -> str:
        timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return f'{ip} - - [{timestamp.strftime("%d/%b/%Y:%H:%M:%S")} +0000] "GET / HTTP/1.1" {status} 10 "-" "curl"\n'

    def _archives_dir(self, container: DependencyContainer) -> Path:
        return container.project_root / "var" / "backups" / "logs"

    # -- Bibliotheque -----------------------------------------------

    async def test_library_add_manual_path_and_remove(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_library(pilot)
            pilot.app.screen.query_one("#path-input", Input).value = str(self.access_log)
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#log-list", DataTable)
            self.assertEqual(table.row_count, 1)

            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#remove", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#log-list", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_library_add_known_logs_from_omega_serv(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_library(pilot)
            pilot.app.screen.query_one("#add-known", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#log-list", DataTable)
            self.assertEqual(table.row_count, 3)

    async def test_library_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_library(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    # -- Favoris ------------------------------------------------------

    async def test_favorites_create_launch_and_delete(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_favorites(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#name-input", Input).value = "mon favori"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            favorites_table = pilot.app.screen.query_one("#favorites-table", DataTable)
            self.assertEqual(favorites_table.row_count, 1)

            favorites_table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogSimpleViewerScreen)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogFavoritesScreen)

            favorites_table = pilot.app.screen.query_one("#favorites-table", DataTable)
            favorites_table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            favorites_table = pilot.app.screen.query_one("#favorites-table", DataTable)
            self.assertEqual(favorites_table.row_count, 0)

    async def test_favorites_launch_lnav_auto_launches_without_extra_click(self):
        """Retour utilisateur 2026-10-15 : "on tombe sur l'ecran suivre les
        logs fusionnes au lieu de lancer directement le favori" - un
        favori lnav doit lancer lnav TOUT DE SUITE (comme le font deja
        les favoris Simple/Classique), jamais exiger un second clic sur
        "Lancer lnav" une fois arrive sur LnavScreen."""
        self.access_log.write_text("line1\n")
        error_log = self.root / "var" / "log" / "error.log"
        error_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        self._add_to_library(container, error_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_favorites(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1,2"
            pilot.app.screen.query_one("#name-input", Input).value = "fusion"
            pilot.app.screen.query_one("#viewer-select", Select).value = "lnav"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            favorites_table = pilot.app.screen.query_one("#favorites-table", DataTable)
            favorites_table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LnavScreen)
            self.assertEqual(len(self.lnav_calls), 1)
            paths, _title, _menu_label = self.lnav_calls[0]
            self.assertEqual(set(paths), {self.access_log, error_log})

    async def test_favorites_rejects_incompatible_viewer(self):
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        self._add_to_library(container, self.root / "var" / "log" / "error.log")
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_favorites(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1,2"
            pilot.app.screen.query_one("#name-input", Input).value = "incompatible"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("seul lnav est compatible", str(pilot.app.screen.query_one("#favorites-error").content))
            favorites_table = pilot.app.screen.query_one("#favorites-table", DataTable)
            self.assertEqual(favorites_table.row_count, 0)

    async def test_favorites_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_favorites(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    # -- Voir les logs (selection + viewers) --------------------------

    async def test_view_logs_simple_opens_simple_viewer_for_single_log(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-simple", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogSimpleViewerScreen)

    async def test_view_logs_classic_opens_classic_viewer_for_single_log(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-classic", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogViewerScreen)

    async def test_view_logs_simple_refused_for_multiple_logs(self):
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        self._add_to_library(container, self.root / "var" / "log" / "error.log")
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1,2"
            pilot.app.screen.query_one("#view-simple", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogViewScreen)
            self.assertIn("seul lnav est compatible", str(pilot.app.screen.query_one("#view-error").content))

    async def test_view_logs_lnav_opens_with_multiple_logs(self):
        self.access_log.write_text("line1\n")
        error_log = self.root / "var" / "log" / "error.log"
        error_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        self._add_to_library(container, error_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1,2"
            pilot.app.screen.query_one("#view-lnav", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LnavScreen)
            self.assertTrue(pilot.app.screen.query_one("#check-preset-0", Checkbox).value)
            self.assertTrue(pilot.app.screen.query_one("#check-preset-1", Checkbox).value)
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertEqual(len(self.lnav_calls), 1)
            paths, _title, _menu_label = self.lnav_calls[0]
            self.assertEqual(set(paths), {self.access_log, error_log})

    async def test_view_logs_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)

    # -- Viewer Simple --------------------------------------------------

    async def test_simple_viewer_shows_parsed_entries_and_stats(self):
        self.access_log.write_text(self._archive_line("1.1.1.1", 1, 200))
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-simple", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#entries-table", DataTable)
            self.assertEqual(table.row_count, 1)
            stats_content = str(pilot.app.screen.query_one("#stats-box", Static).content)
            self.assertIn("1.1.1.1", stats_content)
            # Retour utilisateur 2026-10-15 : "aucun parser, juste les
            # stats http" - #stats-box sans largeur fixe ecrasait la
            # table a 1 colonne de large (invisible a l'ecran) faute de
            # la regle #stats-box { width: 34; } (oubliee lors du
            # portage depuis omega-log, voir base.tcss).
            self.assertGreater(table.size.width, 10)

    async def test_simple_viewer_back_button_returns_to_view_logs_screen(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-simple", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogViewScreen)

    # -- Viewer Classique -----------------------------------------------

    async def _open_classic_viewer(self, pilot, container: DependencyContainer) -> None:
        self._add_to_library(container, self.access_log)
        await self._open_view_logs(pilot)
        pilot.app.screen.query_one("#selection-input", Input).value = "1"
        pilot.app.screen.query_one("#view-classic", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, LogViewerScreen)

    async def test_classic_viewer_shows_missing_file_message(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_classic_viewer(pilot, container)
            self.assertIn("introuvable", str(pilot.app.screen.query_one("#viewer-error").content))
            log_widget = pilot.app.screen.query_one("#log-content", RichLog)
            self.assertEqual(len(log_widget.lines), 0)

    async def test_classic_viewer_shows_existing_lines_and_follows_new_ones(self):
        self.access_log.write_text("line1\nline2\n")
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_classic_viewer(pilot, container)
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
    async def test_classic_viewer_shows_a_clean_error_instead_of_crashing_on_permission_denied(self):
        """Retour utilisateur 2026-09-14 : "j'ai clique sur waf-alerts.log,
        ca a bloque l'application" - un fichier de var/log/ peut
        appartenir au compte systeme dedie du service pendant que la
        session TUI courante n'a pas encore pris en compte l'appartenance
        de groupe qui donnerait normalement l'acces (meme cause deja
        rencontree et corrigee pour Active Defense). Vrai fichier
        reellement illisible (jamais un mock)."""
        self.access_log.write_text("line1\n")
        self.access_log.chmod(0o000)
        try:
            container = self._container()
            self._generate_config(container)
            app = OmegaServApp(container)
            async with app.run_test(size=(120, 45)) as pilot:
                await self._start(pilot)
                await self._open_classic_viewer(pilot, container)
                self.assertIn("Impossible de lire", str(pilot.app.screen.query_one("#viewer-error").content))
                log_widget = pilot.app.screen.query_one("#log-content", RichLog)
                self.assertEqual(len(log_widget.lines), 0)
        finally:
            self.access_log.chmod(0o644)

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions - test non pertinent")
    async def test_classic_viewer_follow_stops_cleanly_if_file_becomes_unreadable(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        try:
            app = OmegaServApp(container)
            async with app.run_test(size=(120, 45)) as pilot:
                await self._start(pilot)
                await self._open_classic_viewer(pilot, container)
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

    async def test_classic_viewer_back_button_returns_to_view_logs_screen(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_classic_viewer(pilot, container)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogViewScreen)

    # -- lnav (checkboxes connues/epingles, via "Voir les logs") --------

    async def test_lnav_additional_known_log_included_alongside_preset(self):
        self.access_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-lnav", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LnavScreen)
            # Le preset (depuis la Bibliotheque) est deja coche par defaut ;
            # on ajoute aussi "error" (connu mais absent) - doit etre
            # signale comme introuvable sans bloquer le lancement.
            pilot.app.screen.query_one("#check-error", Checkbox).value = True
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertEqual(len(self.lnav_calls), 1)
            paths, _title, _menu_label = self.lnav_calls[0]
            self.assertEqual(paths, (self.access_log,))

    async def test_lnav_refuses_when_nothing_selected(self):
        self.access_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#check-preset-0", Checkbox).value = False
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIn("Aucun fichier valide", str(pilot.app.screen.query_one("#lnav-error").content))
            self.assertEqual(len(self.lnav_calls), 0)

    async def test_lnav_magnet_log_selected(self):
        magnet_log = self.root / "var" / "log" / "waf-magnet-alerts.log"
        magnet_log.parent.mkdir(parents=True, exist_ok=True)
        magnet_log.write_text("alerte magnet 1\n")
        self.access_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#check-preset-0", Checkbox).value = False
            pilot.app.screen.query_one("#check-magnet_alerts", Checkbox).value = True
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertEqual(len(self.lnav_calls), 1)
            paths, _title, _menu_label = self.lnav_calls[0]
            self.assertEqual(paths, (magnet_log,))

    async def test_lnav_pin_check_launch_then_unpin(self):
        extra_log = self.root / "extra.log"
        extra_log.write_text("ligne externe\n")
        self.access_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#check-preset-0", Checkbox).value = False

            pilot.app.screen.query_one("#manual-path-input", Input).value = str(extra_log)
            pilot.app.screen.query_one("#pin-manual", Button).press()
            await pilot.pause()
            pinned_checkbox = pilot.app.screen.query_one("#check-pinned-0", Checkbox)
            pinned_checkbox.value = True
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertEqual(len(self.lnav_calls), 1)
            paths, _title, _menu_label = self.lnav_calls[0]
            self.assertEqual(paths, (extra_log,))

            pilot.app.screen.query_one("#unpin-select", Select).value = str(extra_log)
            await pilot.pause()
            pilot.app.screen.query_one("#unpin", Button).press()
            await pilot.pause()
            with self.assertRaises(NoMatches):
                pilot.app.screen.query_one("#check-pinned-0", Checkbox)

    async def test_lnav_unavailable_without_injected_runner(self):
        self.access_log.write_text("line1\n")
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#launch", Button).press()
            await pilot.pause()
            self.assertIn("indisponible", str(pilot.app.screen.query_one("#lnav-error").content))

    async def test_lnav_back_button_returns_to_view_logs_screen(self):
        self.access_log.write_text("line1\n")
        container = self._container(lnav_runner=self._fake_lnav_runner)
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_view_logs(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#view-lnav", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogViewScreen)

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

    # -- Rotation / archivage / restauration / purge / export -----------
    # (colonne MAINTENANCE, inchangee par la refonte du menu)

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

    # -- Voir et traiter IP (generalise a la Bibliotheque) --------------

    async def test_process_ip_lists_and_removes_selected_ip(self):
        self.access_log.write_text(self._archive_line("1.1.1.1", 2, 200) + self._archive_line("2.2.2.2", 1, 200))
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_process_ip(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#period-all", Button).press()
            await pilot.pause()
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
            self.assertIsInstance(pilot.app.screen, ProcessIpScreen)
            table = pilot.app.screen.query_one("#top-ips-table", DataTable)
            self.assertEqual(table.row_count, 1)
        self.assertNotIn("1.1.1.1", self.access_log.read_text())
        self.assertIn("2.2.2.2", self.access_log.read_text())

    async def test_process_ip_period_7d_excludes_older_entries(self):
        self.access_log.write_text(self._archive_line("1.1.1.1", 2, 200) + self._archive_line("2.2.2.2", 24 * 10, 200))
        container = self._container()
        self._generate_config(container)
        self._add_to_library(container, self.access_log)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_process_ip(pilot)
            pilot.app.screen.query_one("#selection-input", Input).value = "1"
            pilot.app.screen.query_one("#period-7d", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#top-ips-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(str(table.get_row_at(0)[0]), "1.1.1.1")

    async def test_process_ip_back_button_returns_to_logs_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._start(pilot)
            await self._open_process_ip(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LogsMenuScreen)


if __name__ == "__main__":
    unittest.main()
