"""Tests d'integration de l'ecran Etat & Ressources (retour utilisateur
2026-09-09, remplace "Simuler une requete" comme raccourci direct du
menu principal - reintroduit ici en bouton). `ServiceManagerPort` double
en memoire (`FakeServiceManager`, reutilise depuis test_tui_service.py) ;
`collect_system_stats()` reste la vraie fonction psutil (sondage
systeme reel, aucun mock d'une bibliotheque dont le seul travail est de
lire de vraies statistiques - meme discipline que
test_openssl_certificate_tool.py)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textual.widgets import Button, Input, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.services.pid_file import write_pid_file
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import Option
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.persistence.snapshots import SnapshotMetadata
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.log_simple_viewer_screen import LogSimpleViewerScreen
from omega_serv.interfaces.tui.screens.resource_status_screen import ResourceStatusScreen
from omega_serv.interfaces.tui.screens.simulate_request_screen import SimulateRequestScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from tests.integration.test_tui_service import FakeServiceManager

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiResourceStatus(unittest.IsolatedAsyncioTestCase):
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
        kwargs.setdefault("instance_registry_path", self.root / "instances.json")  # jamais le vrai registre
        return DependencyContainer(project_root=self.root, **kwargs)

    def _generate_config(self, container: DependencyContainer) -> None:
        generate_default_config(container.configuration, container.filesystem, container.config_file)

    async def _open_resource_status(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#resource-status", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ResourceStatusScreen)
        # ETAT DU SERVEUR et RESSOURCES SYSTEME sont calcules dans des
        # threads de travail (retour utilisateur 2026-09-21/26, gel total
        # reproduit sinon) - attendre explicitement leur fin plutot que de
        # compter sur la vitesse d'un seul pilot.pause(), sinon flaky des
        # que l'un des deux threads met plus de quelques microsecondes.
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

    async def test_all_three_boxes_are_populated_on_mount(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            screen = pilot.app.screen
            state_text = screen.query_one("#box-server-state", Static).render().plain
            traffic_text = screen.query_one("#box-traffic", Static).render().plain
            system_text = screen.query_one("#box-system", Static).render().plain

            self.assertIn("PROCESSUS", state_text)
            self.assertIn("ARRÊTÉ", state_text)
            self.assertIn("standard", state_text)  # profil par defaut de generate_default_config
            self.assertIn("Aucune sauvegarde", state_text)
            self.assertRegex(state_text, r"Nombre\s+: 1")  # l'instance courante, meme hors registre
            self.assertLess(state_text.index("MOTEUR HTTP"), state_text.index("CONFIGURATION OPTIONS"))
            self.assertLess(state_text.index("CONFIGURATION OPTIONS"), state_text.index("Options actives"))
            self.assertIn("INTERFACES", system_text)
            self.assertRegex(state_text, rf"Cette instance\s+: {self.root.resolve().name}")
            self.assertLess(state_text.index("SERVICE SYSTÈME"), state_text.index("INSTANCE"))
            self.assertLess(state_text.index("INSTANCE"), state_text.index("SAUVEGARDE"))
            self.assertLess(state_text.index("SERVICE SYSTÈME"), state_text.index("SAUVEGARDE"))
            self.assertLess(state_text.index("SAUVEGARDE"), state_text.index("CONFIGURATION ACTIVE"))

            self.assertIn("RENDEMENT", traffic_text)
            self.assertRegex(traffic_text, r"Total\s+: 0")

            self.assertIn("CPU", system_text)
            self.assertIn("RAM", system_text)
            self.assertIn("Uptime", system_text)

    async def test_instance_section_lists_current_then_running_at_most_three(self):
        container = self._container()
        self._generate_config(container)
        created = datetime(2026, 11, 1, tzinfo=timezone.utc)
        others = {}
        for name in ("arret-a", "arret-b", "marche", "arret-c"):
            others[name] = self.root.parent / f"{self.root.name}-{name}"
            (others[name] / "var" / "run").mkdir(parents=True, exist_ok=True)
            self.addCleanup(shutil.rmtree, others[name], True)
        write_pid_file(container.filesystem, others["marche"] / "var" / "run" / "omega-serv.pid", os.getpid())
        entries = [InstanceEntry(name, path.resolve(), "127.0.0.1", 9000 + i, f"omega-serv-{name}", created)
                   for i, (name, path) in enumerate(others.items())]
        entries.insert(2, InstanceEntry("principale", self.root.resolve(), "127.0.0.1", 8080, "omega-serv", created))
        container.instance_registry.save(entries)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertRegex(state_text, r"Nombre\s+: 5")
            self.assertRegex(state_text, r"Cette instance\s+: principale")
            self.assertRegex(state_text, r"principale \(courante\)\s+: arrêtée")
            self.assertRegex(state_text, rf"marche\s+: PID {os.getpid()}")
            self.assertLess(state_text.index("principale (courante)"), state_text.index("marche "))
            self.assertIn("+ 2 autre(s)", state_text)
            self.assertEqual(state_text.count("arret-"), 1)

    async def test_unregistered_current_instance_is_counted_and_listed_first(self):
        container = self._container()
        self._generate_config(container)
        other = self.root.parent / f"{self.root.name}-autre"
        (other / "var" / "run").mkdir(parents=True)
        self.addCleanup(shutil.rmtree, other, True)
        container.instance_registry.save([InstanceEntry(
            "autre", other.resolve(), "127.0.0.1", 9000, "omega-serv-autre", datetime(2026, 11, 1, tzinfo=timezone.utc))])
        write_pid_file(container.filesystem, self.root / "var" / "run" / "omega-serv.pid", os.getpid())
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            current = self.root.resolve().name
            self.assertRegex(state_text, r"Nombre\s+: 2")
            self.assertRegex(state_text, rf"{current} \(courante\)\s+: PID {os.getpid()}")
            self.assertRegex(state_text, r"autre\s+: arrêtée")

    async def test_backup_section_shows_latest_date_and_count(self):
        container = self._container()
        self._generate_config(container)
        store = container.build_backup_metadata_store(self.root / "var" / "backups" / "config-snapshots")
        for day in (1, 3, 2):
            created = datetime(2026, 11, day, 10, 30, tzinfo=timezone.utc)
            store.save(SnapshotMetadata(snapshot_id=f"snapshot_{day}", created_at=created, scope="config"))
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            latest = datetime(2026, 11, 3, 10, 30, tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
            self.assertRegex(state_text, rf"Dernière\s+: {latest}")
            self.assertRegex(state_text, r"Nombre\s+: 3")

    async def test_pid_file_with_live_process_shows_started(self):
        container = self._container()
        self._generate_config(container)
        pid_path = self.root / "var" / "run" / "omega-serv.pid"
        write_pid_file(container.filesystem, pid_path, os.getpid())
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertIn("DÉMARRÉ", state_text)

    async def test_sent_volume_counts_only_responses_since_the_server_started(self):
        container = self._container()
        self._generate_config(container)
        write_pid_file(container.filesystem, self.root / "var" / "run" / "omega-serv.pid", os.getpid())
        now = datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000")
        access_log = self.root / "var" / "log" / "access.log"
        access_log.parent.mkdir(parents=True, exist_ok=True)
        access_log.write_text(
            '9.9.9.9 - - [01/Jan/2020:00:00:00 +0000] "GET /old HTTP/1.1" 200 512000 "-" "ua"\n'  # avant le demarrage
            f'1.1.1.1 - - [{now}] "GET /a HTTP/1.1" 200 1024 "-" "ua"\n'
            f'1.1.1.1 - - [{now}] "GET /b HTTP/1.1" 200 1024 "-" "ua"\n')
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            for _round in range(3):  # releve du demarrage, calcul du volume, puis affichage
                pilot.app.screen.query_one("#refresh", Button).press()
                await pilot.pause()
                await pilot.app.workers.wait_for_complete()
                await pilot.pause()
            system_text = pilot.app.screen.query_one("#box-system", Static).render().plain
            self.assertRegex(system_text, r"Envoyé\s+: 2\.0 Ko")
            self.assertIn("(réponses depuis le démarrage)", system_text)
            self.assertRegex(system_text, r"Charge\s+: [\d.]+ [\d.]+ [\d.]+ \(\d+ cœurs\)")

    async def test_access_log_button_opens_the_simple_viewer_directly(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            pilot.app.screen.query_one("#open-access-log", Button).press()
            await pilot.pause()
            viewer = pilot.app.screen
            self.assertIsInstance(viewer, LogSimpleViewerScreen)
            self.assertEqual(viewer._path, str(self.root / "var" / "log" / "access.log"))
            viewer.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ResourceStatusScreen)

    async def test_stale_pid_file_shows_stopped(self):
        container = self._container()
        self._generate_config(container)
        pid_path = self.root / "var" / "run" / "omega-serv.pid"
        write_pid_file(container.filesystem, pid_path, 999999)  # PID improbable, non vivant
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertIn("ARRÊTÉ", state_text)
            self.assertIn("obsolète", state_text)

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions Unix")
    async def test_unreadable_pid_file_shows_unknown_not_stopped(self):
        container = self._container()
        self._generate_config(container)
        pid_path = self.root / "var" / "run" / "omega-serv.pid"
        write_pid_file(container.filesystem, pid_path, os.getpid())
        pid_path.chmod(0o000)
        try:
            app = OmegaServApp(container)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._open_resource_status(pilot)
                state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
                self.assertIn("à confirmer", state_text)
                self.assertIn("rien d'alarmant", state_text)
                self.assertNotIn("ARRÊTÉ", state_text)
        finally:
            pid_path.chmod(0o600)

    async def test_service_manager_status_shown_when_active(self):
        manager = FakeServiceManager()
        manager.start("omega-serv")
        container = self._container(service_manager_factory=lambda: manager)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertRegex(state_text, r"Actif\s+: True")

    async def test_service_manager_status_reflects_renamed_service(self):
        manager = FakeServiceManager(known_service="mon-service-renomme")
        manager.start("mon-service-renomme")
        container = self._container(service_manager_factory=lambda: manager)
        container.settings_store.set("service_name", "mon-service-renomme")
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertRegex(state_text, r"Actif\s+: True")

    async def test_renaming_in_service_screen_is_reflected_here_end_to_end(self):
        manager = FakeServiceManager(known_service="mon-service-renomme")
        manager.start("mon-service-renomme")
        container = self._container(service_manager_factory=lambda: manager)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("x")
            await pilot.pause()
            if isinstance(pilot.app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
                await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)
            pilot.app.screen.query_one("#service", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#service-name", Input).value = "mon-service-renomme"
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)

            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertRegex(state_text, r"Actif\s+: True")

    async def test_refresh_button_picks_up_new_log_lines(self):
        container = self._container()
        self._generate_config(container)
        (self.root / "var" / "log").mkdir(parents=True)
        access_log = self.root / "var" / "log" / "access.log"
        access_log.write_text("")
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            with access_log.open("a") as f:
                f.write(
                    '203.0.113.10 - - [09/Sep/2026:12:00:00 +0000] '
                    '"GET /index.html HTTP/1.1" 200 156 "-" "curl" req1\n'
                )
                f.write(
                    '203.0.113.11 - - [09/Sep/2026:12:00:01 +0000] '
                    '"GET /missing HTTP/1.1" 404 0 "-" "curl" req2\n'
                )
            pilot.app.screen.query_one("#refresh", Button).press()
            await pilot.pause()
            traffic_text = pilot.app.screen.query_one("#box-traffic", Static).render().plain
            self.assertRegex(traffic_text, r"Total\s+: 2")
            self.assertRegex(traffic_text, r"IPs\ uniques\s+: 2")

    async def test_simulate_request_shortcut_reachable_and_returns(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            pilot.app.screen.query_one("#simulate-request", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, SimulateRequestScreen)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ResourceStatusScreen)

    async def test_back_button_returns_home(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)


if __name__ == "__main__":
    unittest.main()

    async def test_history_security_and_omega_serv_sections(self):
        """2026-11-05 : 15 min relues a l'ouverture, alertes du WAF comptees, section OMEGA-SERV."""
        container = self._container()
        self._generate_config(container)
        result = load_config(container.configuration, container.config_file)
        assert result.config is not None
        options = dict(result.config.options)
        options["waf"] = Option(name="waf", enabled=True, settings={})
        container.configuration.save(container.config_file, replace(result.config, options=options))
        log_dir = self.root / "var" / "log"
        log_dir.mkdir(parents=True)
        now = datetime.now(timezone.utc)

        def line(when: datetime, path: str, status: int) -> str:
            return (f'198.51.100.7 - - [{when.strftime("%d/%b/%Y:%H:%M:%S +0000")}] '
                    f'"GET {path} HTTP/1.1" {status} 10 "-" "curl" r\n')

        (log_dir / "access.log").write_text(
            line(now - timedelta(hours=2), "/trop-vieux", 200)
            + line(now - timedelta(minutes=3), "/wp-admin", 404)
            + line(now - timedelta(seconds=20), "/", 200))
        (log_dir / "waf-alerts.log").write_text(json.dumps({
            "timestamp": (now - timedelta(minutes=2)).isoformat(), "request_id": "r1", "remote_ip": "198.51.100.7",
            "action": "block", "stage": "inspection", "score": 8, "rules": ["R"],
            "findings": [{"id": "R", "pack": "scan-paths"}]}) + "\n")
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 60)) as pilot:
            await self._open_resource_status(pilot)
            screen = pilot.app.screen
            traffic = screen.query_one("#box-traffic", Static).render().plain
            self.assertRegex(traffic, r"Total\s+: 2")  # la ligne d'il y a 2 h n'est pas relue
            self.assertIn("/wp-admin", traffic)
            self.assertNotIn("/trop-vieux", traffic)
            self.assertRegex(traffic, r"Attaques bloquées\s+: 1")
            system = screen.query_one("#box-system", Static).render().plain
            self.assertIn("OMEGA-SERV", system)
            self.assertIn("arrêté", system)
            self.assertIn("mesure en cours", system)
            pilot.app.screen.query_one("#refresh", Button).press()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            system = screen.query_one("#box-system", Static).render().plain
            self.assertIn("/s", system.split("Débit", 1)[1].split("\n", 1)[0])

