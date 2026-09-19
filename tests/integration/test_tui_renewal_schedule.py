"""Tests d'integration Phase 5 de l'assistant TLS (etude
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md) : sous-ecran Renouvellement
automatique Certbot. `FakeServiceManager` reutilise de test_tui_service.py
(meme precedent que test_tui_instances.py/test_tui_resource_status.py) -
jamais de vrai systemctl/sudo/crontab dans une suite automatisee."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Static

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.renewal_schedule_screen import RenewalScheduleScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.screens.tls_menu_screen import TlsMenuScreen
from omega_serv.ports.process_runner_port import ProcessResult
from tests.integration.test_tui_service import FakeServiceManager

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _FakeProcessRunner:
    def __init__(self, *, crontab_available: bool = True, crontab_content: str = "") -> None:
        self._crontab_available = crontab_available
        self.crontab_content = crontab_content
        self.calls: list[list[str]] = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append(args)
        if not self._crontab_available:
            return ProcessResult(returncode=127, stdout="", stderr=f"{args[0]} : commande introuvable")
        if args == ["crontab", "-l"]:
            return ProcessResult(returncode=0, stdout=self.crontab_content, stderr="")
        if args == ["crontab", "-"]:
            self.crontab_content = input_text or ""
            return ProcessResult(returncode=0, stdout="", stderr="")
        raise AssertionError(f"appel inattendu : {args}")

    def run_interactive(self, args):
        raise NotImplementedError


class _PermissiveSystemdManager:
    """Double minimal, distinct de FakeServiceManager (test_tui_service.py) :
    accepte n'importe quel nom d'unite (write_unit_file/enable/start),
    utile uniquement pour verifier que DEUX instances ecrivent bien des
    unites de noms differents sur le meme manager - jamais utilise pour
    tester le comportement d'UNE unite en particulier (les autres tests
    de ce fichier gardent FakeServiceManager et son garde-fou
    _check_known)."""

    def __init__(self) -> None:
        self.unit_files: dict[Path, str] = {}

    def manager_type(self):
        return "systemd"

    def write_unit_file(self, unit_path, content):
        self.unit_files[unit_path] = content

    def reload_daemon(self):
        return True

    def enable(self, service_name):
        return True

    def start(self, service_name):
        return True

    def is_active(self, service_name):
        return False

    def is_enabled(self, service_name):
        return False


class TestTuiRenewalSchedule(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.systemd_unit_dir = self.root.parent / f"{self.root.name}-etc-systemd-system"
        self.systemd_unit_dir.mkdir()
        self.addCleanup(shutil.rmtree, self.systemd_unit_dir, ignore_errors=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, *, manager=None, process_runner=None) -> DependencyContainer:
        self._acme_runner = process_runner or _FakeProcessRunner()
        service_factory = (lambda: manager) if manager is not None else None
        return DependencyContainer(
            project_root=self.root, service_manager_factory=service_factory,
            systemd_unit_dir=self.systemd_unit_dir, acme_client_factory=lambda: self._acme_runner,
        )

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_screen(self, pilot) -> None:
        while not isinstance(pilot.app.screen, HomeScreen):
            await pilot.press("escape")
            await pilot.pause()
            if isinstance(pilot.app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
                await pilot.pause()
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
        pilot.app.screen.query_one("#tls", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, TlsMenuScreen)
        pilot.app.screen.query_one("#renewal-schedule", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, RenewalScheduleScreen)

    async def test_back_button_returns_to_tls_menu(self):
        container = self._container(manager=FakeServiceManager())
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_screen(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TlsMenuScreen)

    async def test_systemd_status_shows_not_installed_then_installed(self):
        manager = FakeServiceManager(known_service="omega-serv-certbot-renew.timer")
        container = self._container(manager=manager)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_screen(pilot)
            self.assertIn("non installe", str(pilot.app.screen.query_one("#status-text", Static).content))

            pilot.app.screen.query_one("#configure", Button).press()
            await pilot.pause()
            self.assertIn("installe et actif", str(pilot.app.screen.query_one("#status-text", Static).content))

        self.assertIn(self.systemd_unit_dir / "omega-serv-certbot-renew.service", manager.unit_files)
        self.assertIn(self.systemd_unit_dir / "omega-serv-certbot-renew.timer", manager.unit_files)
        self.assertIn(("reload-daemon", ""), manager.calls)

    async def test_cron_used_when_no_systemd(self):
        runner = _FakeProcessRunner()
        container = self._container(manager=FakeServiceManager(manager_type="openrc"), process_runner=runner)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_screen(pilot)
            pilot.app.screen.query_one("#configure", Button).press()
            await pilot.pause()
            self.assertIn("crontab", str(pilot.app.screen.query_one("#status-text", Static).content))
        self.assertIn("omega-serv-certbot-renew", runner.crontab_content)

    async def test_manual_instructions_when_no_mechanism_available(self):
        runner = _FakeProcessRunner(crontab_available=False)
        container = self._container(manager=None, process_runner=runner)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_screen(pilot)
            pilot.app.screen.query_one("#configure", Button).press()
            await pilot.pause()
            status_text = str(pilot.app.screen.query_one("#status-text", Static).content)
            self.assertIn("certbot renew", status_text)
            self.assertIn("vous-meme", status_text.lower())

    async def test_two_instances_never_collide(self):
        manager = _PermissiveSystemdManager()
        container_a = DependencyContainer(
            project_root=self.root, service_manager_factory=lambda: manager,
            systemd_unit_dir=self.systemd_unit_dir, acme_client_factory=lambda: _FakeProcessRunner(),
        )
        app_a = OmegaServApp(container_a)
        async with app_a.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_screen(pilot)
            pilot.app.screen.query_one("#configure", Button).press()
            await pilot.pause()

        other_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, other_root, ignore_errors=True)
        (other_root / "webroot").mkdir()
        (other_root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, other_root / "config" / "profiles" / profile_file.name)

        container_b = DependencyContainer(
            project_root=other_root, service_manager_factory=lambda: manager,
            systemd_unit_dir=self.systemd_unit_dir, acme_client_factory=lambda: _FakeProcessRunner(),
        )
        container_b.settings_store.set("service_name", "omega-serv-monsite")
        app_b = OmegaServApp(container_b)
        async with app_b.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_screen(pilot)
            pilot.app.screen.query_one("#configure", Button).press()
            await pilot.pause()

        self.assertIn(self.systemd_unit_dir / "omega-serv-certbot-renew.timer", manager.unit_files)
        self.assertIn(self.systemd_unit_dir / "omega-serv-monsite-certbot-renew.timer", manager.unit_files)


if __name__ == "__main__":
    unittest.main()
