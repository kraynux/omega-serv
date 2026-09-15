# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration de l'ecran Etat & Ressources (retour utilisateur
2026-09-09, remplace "Simuler une requete" comme raccourci direct du
menu principal - reintroduit ici en bouton). `ServiceManagerPort` double
en memoire (`FakeServiceManager`, reutilise depuis test_tui_service.py) ;
`collect_system_stats()` reste la vraie fonction psutil (sondage
systeme reel, aucun mock d'une bibliotheque dont le seul travail est de
lire de vraies statistiques - meme discipline que
test_openssl_certificate_tool.py)."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Input, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.services.pid_file import write_pid_file
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.home import HomeScreen
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
            self.assertIn("ARRETE", state_text)
            self.assertIn("standard", state_text)  # profil par defaut de generate_default_config

            self.assertIn("RENDEMENT", traffic_text)
            self.assertIn("Total    : 0", traffic_text)

            self.assertIn("CPU", system_text)
            self.assertIn("RAM", system_text)
            self.assertIn("Uptime", system_text)

    async def test_pid_file_with_live_process_shows_started(self):
        container = self._container()
        self._generate_config(container)
        pid_path = self.root / "var" / "run" / "omega-serv.pid"
        write_pid_file(container.filesystem, pid_path, os.getpid())
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertIn("DEMARRE", state_text)

    async def test_stale_pid_file_shows_stopped(self):
        container = self._container()
        self._generate_config(container)
        pid_path = self.root / "var" / "run" / "omega-serv.pid"
        write_pid_file(container.filesystem, pid_path, 999999)  # PID improbable, non vivant
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertIn("ARRETE", state_text)
            self.assertIn("obsolete", state_text)

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions Unix")
    async def test_unreadable_pid_file_shows_unknown_not_stopped(self):
        # Retour utilisateur 2026-09-10, second retour immediat sur le
        # meme bug (var/ partagee avec le compte de service dedie) :
        # "Installer l'unite" puis "Demarrer" fonctionnaient reellement
        # (connexion possible), mais cet ecran affichait quand meme
        # "ARRETE" - trompeur pendant la fenetre exacte ou le fichier
        # PID appartient au compte dedie et la session interactive n'a
        # pas encore ete reconnectee pour beneficier du nouveau groupe.
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
                # Retour utilisateur 2026-09-10 (suite) : le libelle
                # "INCONNU (fichier PID illisible)" inquietait a tort -
                # reformule en ton rassurant, "rien d'alarmant"/"normal".
                self.assertIn("a confirmer", state_text)
                self.assertIn("rien d'alarmant", state_text)
                self.assertNotIn("ARRETE", state_text)
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
            self.assertIn("Actif   : True", state_text)

    async def test_service_manager_status_reflects_renamed_service(self):
        # Bug latent corrige : ce panneau interrogeait toujours
        # "omega-serv" en dur, jamais le nom reellement configure dans
        # l'ecran SERVICE (settings_store, var/settings.json).
        manager = FakeServiceManager(known_service="mon-service-renomme")
        manager.start("mon-service-renomme")
        container = self._container(service_manager_factory=lambda: manager)
        container.settings_store.set("service_name", "mon-service-renomme")
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(160, 50)) as pilot:
            await self._open_resource_status(pilot)
            state_text = pilot.app.screen.query_one("#box-server-state", Static).render().plain
            self.assertIn("Actif   : True", state_text)

    async def test_renaming_in_service_screen_is_reflected_here_end_to_end(self):
        # Meme correction, verifiee cette fois de bout en bout a travers
        # les DEUX ecrans reels dans la MEME session (jamais en ecrivant
        # directement dans settings_store) - la preuve la plus honnete
        # que la synchronisation fonctionne reellement via l'interface.
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
            self.assertIn("Actif   : True", state_text)

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
            self.assertIn("Total    : 2", traffic_text)
            self.assertIn("IPs uniques   : 2", traffic_text)

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
