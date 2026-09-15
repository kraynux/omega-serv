# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase II de l'interface (plan interface §12,
menu 5) : ecran Service - statut, start/stop/restart/enable/disable,
installation/desinstallation de l'unite systemd. `ServiceManagerPort`
double en memoire (pas de vrai `systemctl`/`sudo` en test, voir
application/services/build_service_manager.py - la fabrique reelle
n'est jamais appelee ici, un double est injecte via
`DependencyContainer(service_manager_factory=...)`)."""
from __future__ import annotations

import getpass
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Input, Static

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.service_screen import ServiceScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.ports.service_manager_port import ServiceManagerType

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FakeServiceManager:
    def __init__(self, *, manager_type: ServiceManagerType = "systemd", known_service: str = "omega-serv"):
        self._manager_type = manager_type
        self._known_service = known_service
        self.calls: list[tuple[str, str]] = []
        self._active = False
        self._enabled = False
        self.unit_files: dict[Path, str] = {}

    def manager_type(self) -> ServiceManagerType:
        return self._manager_type

    def _check_known(self, service_name: str) -> None:
        if service_name != self._known_service:
            raise ServiceNotFoundError(service_name, self._manager_type)

    def start(self, service_name: str) -> bool:
        self._check_known(service_name)
        self.calls.append(("start", service_name))
        self._active = True
        return True

    def stop(self, service_name: str) -> bool:
        self._check_known(service_name)
        self.calls.append(("stop", service_name))
        self._active = False
        return True

    def restart(self, service_name: str) -> bool:
        self._check_known(service_name)
        self.calls.append(("restart", service_name))
        return True

    def reload(self, service_name: str) -> bool:
        self._check_known(service_name)
        self.calls.append(("reload", service_name))
        return True

    def enable(self, service_name: str) -> bool:
        self._check_known(service_name)
        self.calls.append(("enable", service_name))
        self._enabled = True
        return True

    def disable(self, service_name: str) -> bool:
        self._check_known(service_name)
        self.calls.append(("disable", service_name))
        self._enabled = False
        return True

    def status(self, service_name: str) -> ServiceStatus:
        self._check_known(service_name)
        return ServiceStatus(
            service_name=service_name,
            active=self._active,
            enabled=self._enabled,
            state="active" if self._active else "inactive",
            sub_state="running" if self._active else "dead",
            description="OMEGA-SERV web server",
        )

    def is_active(self, service_name: str) -> bool:
        return self._active

    def is_enabled(self, service_name: str) -> bool:
        return self._enabled

    def is_available(self) -> bool:
        return True

    def reload_daemon(self) -> bool:
        self.calls.append(("reload-daemon", ""))
        return True

    def write_unit_file(self, unit_path: Path, content: str) -> None:
        self.unit_files[unit_path] = content

    def remove_unit_file(self, unit_path: Path) -> None:
        if unit_path not in self.unit_files:
            raise ServiceControlError(str(unit_path), "remove-unit-file", "absente", self._manager_type)
        del self.unit_files[unit_path]

    def create_system_user(self, user: str, group: str) -> None:
        self.calls.append(("create-system-user", f"{user}:{group}"))

    def remove_system_user(self, user: str, group: str) -> None:
        self.calls.append(("remove-system-user", f"{user}:{group}"))

    def grant_directory_access(self, path: Path, group: str, extra_user: str) -> None:
        self.calls.append(("grant-directory-access", f"{path}:{group}:{extra_user}"))


class TestTuiService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        # Repertoire d'unites systemd FACTICE - retour utilisateur
        # 2026-09-10 (garde-fous multi-instance) : jamais le vrai
        # /etc/systemd/system/ de la machine de test, qui peut deja
        # contenir une vraie unite omega-serv installee ailleurs dans
        # cette session et fausserait silencieusement ces tests.
        self.systemd_unit_dir = self.root.parent / f"{self.root.name}-etc-systemd-system"
        self.systemd_unit_dir.mkdir()
        self.addCleanup(shutil.rmtree, self.systemd_unit_dir, ignore_errors=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, manager: FakeServiceManager | None) -> DependencyContainer:
        factory = (lambda: manager) if manager is not None else (lambda: None)
        return DependencyContainer(
            project_root=self.root, service_manager_factory=factory, systemd_unit_dir=self.systemd_unit_dir,
        )

    async def _reach_service_screen(self, pilot):
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#service", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServiceScreen)

    async def test_no_manager_detected_disables_mutating_buttons(self):
        app = OmegaServApp(self._container(None))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            self.assertIn("Aucun gestionnaire", str(pilot.app.screen.query_one("#service-status").content))
            self.assertTrue(pilot.app.screen.query_one("#start", Button).disabled)
            self.assertTrue(pilot.app.screen.query_one("#install", Button).disabled)

    async def test_non_systemd_manager_disables_install_uninstall_only(self):
        manager = FakeServiceManager(manager_type="openrc")
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            self.assertFalse(pilot.app.screen.query_one("#start", Button).disabled)
            self.assertTrue(pilot.app.screen.query_one("#install", Button).disabled)
            self.assertTrue(pilot.app.screen.query_one("#uninstall", Button).disabled)
            # Retour utilisateur 2026-09-10 : le texte d'aide sur l'unite
            # systemd (compte dedie, partage de var/...) n'a de sens que
            # pour systemd - un gestionnaire different doit voir un texte
            # court et distinct, jamais le meme paragraphe.
            hint = str(pilot.app.screen.query_one("#journey-hint", Static).content)
            self.assertIn("OPENRC", hint)
            self.assertIn("guide d'aide", hint)
            self.assertNotIn("compte", hint)

    async def test_systemd_manager_shows_systemd_journey_hint(self):
        manager = FakeServiceManager()
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            hint = str(pilot.app.screen.query_one("#journey-hint", Static).content)
            self.assertIn("SYSTEMD uniquement", hint)
            self.assertIn("Installer l'unite", hint)
            self.assertIn("Demarrer", hint)

    async def test_start_stop_updates_status_and_calls_manager(self):
        manager = FakeServiceManager()
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#start", Button).press()
            await pilot.pause()
            self.assertIn(("start", "omega-serv"), manager.calls)
            self.assertIn("Actif : True", str(pilot.app.screen.query_one("#service-status").content))

            pilot.app.screen.query_one("#stop", Button).press()
            await pilot.pause()
            self.assertIn(("stop", "omega-serv"), manager.calls)
            self.assertIn("Actif : False", str(pilot.app.screen.query_one("#service-status").content))

    async def test_reload_button_calls_manager_without_toggling_active_state(self):
        # Retour utilisateur 2026-09-11 : distinct de "Redemarrer" -
        # garde les connexions actives, relit seulement la config deja
        # codee cote applicatif (SIGHUP via ExecReload=).
        manager = FakeServiceManager()
        manager.start("omega-serv")
        manager.calls.clear()
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#reload", Button).press()
            await pilot.pause()
            self.assertIn(("reload", "omega-serv"), manager.calls)
            self.assertIn("Actif : True", str(pilot.app.screen.query_one("#service-status").content))

    async def test_enable_disable_calls_manager(self):
        manager = FakeServiceManager()
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            self.assertIn(("enable", "omega-serv"), manager.calls)
            pilot.app.screen.query_one("#disable", Button).press()
            await pilot.pause()
            self.assertIn(("disable", "omega-serv"), manager.calls)

    async def test_unknown_service_name_shows_error_status(self):
        manager = FakeServiceManager(known_service="autre-service")
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            status = str(pilot.app.screen.query_one("#service-status").content)
            self.assertNotIn("Actif", status)

    async def test_install_requires_confirmation_then_writes_unit_file(self):
        manager = FakeServiceManager()
        container = self._container(manager)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#install", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServiceScreen)

        unit_path = container.systemd_unit_dir / "omega-serv.service"
        self.assertIn(unit_path, manager.unit_files)
        self.assertIn("ExecStart=", manager.unit_files[unit_path])
        self.assertIn(("reload-daemon", ""), manager.calls)
        # Retour utilisateur 2026-09-10, vrai bug trouve : le compte
        # systeme dedie n'etait jamais cree, le service echouant a
        # chaque demarrage - doit etre cree AVANT l'ecriture de l'unite.
        self.assertIn(("create-system-user", "omega-serv:omega-serv"), manager.calls)
        self.assertLess(
            manager.calls.index(("create-system-user", "omega-serv:omega-serv")),
            manager.calls.index(("reload-daemon", "")),
        )
        # Second vrai bug trouve juste apres le premier, meme retour
        # utilisateur : le compte cree n'avait toujours aucun droit
        # d'ecriture sur var/ (journalctl a montre un PermissionError,
        # service en boucle de redemarrage) - doit aussi survenir avant
        # l'ecriture de l'unite, meme geste d'installation.
        grant_calls = [c for c in manager.calls if c[0] == "grant-directory-access"]
        self.assertEqual(len(grant_calls), 1)
        self.assertTrue(grant_calls[0][1].endswith(f"var:omega-serv:{getpass.getuser()}"))
        self.assertLess(manager.calls.index(grant_calls[0]), manager.calls.index(("reload-daemon", "")))

    async def test_install_cancelled_does_not_write_unit_file(self):
        manager = FakeServiceManager()
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#install", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
        self.assertEqual(manager.unit_files, {})

    async def test_install_blocked_when_another_unit_shares_this_directory(self):
        # Retour utilisateur 2026-09-10 : garde-fou multi-instance,
        # sens 1 - une AUTRE unite (nom different) pointant deja vers ce
        # meme repertoire projet doit bloquer AVANT le dialogue de
        # confirmation, jamais silencieusement laisser creer un conflit.
        manager = FakeServiceManager()
        container = self._container(manager)
        (container.systemd_unit_dir / "omega-serv-old.service").write_text(
            f"[Service]\nWorkingDirectory={container.project_root}\n"
        )
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#install", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServiceScreen)
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("omega-serv-old" in m for m in messages))
        self.assertEqual(manager.unit_files, {})

    async def test_install_blocked_when_name_already_used_by_another_directory(self):
        # Sens 2, meme retour utilisateur : ce nom de service est deja
        # utilise par une unite pointant vers un AUTRE repertoire -
        # l'installer ici volerait le nom (ecraserait cette unite).
        manager = FakeServiceManager()
        container = self._container(manager)
        (container.systemd_unit_dir / "omega-serv.service").write_text(
            "[Service]\nWorkingDirectory=/home/kraynux/DEV/SERV2/omega-serv\n"
        )
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#install", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServiceScreen)
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("SERV2" in m for m in messages))
        self.assertEqual(manager.unit_files, {})

    async def test_uninstall_confirmed_reaches_use_case_without_crashing(self):
        # `uninstall_systemd_service` verifie l'existence du fichier
        # d'unite via le VRAI FilesystemPort du conteneur (jamais via le
        # double de ServiceManagerPort - meme sur un systeme reel, c'est
        # `write_unit_file`/`sudo tee` qui ecrit sur disque, la
        # verification d'existence reste un simple `Path.exists()`) :
        # ici, aucune unite n'existe reellement sur la machine de test,
        # la branche "introuvable" est donc la sortie attendue - le test
        # verifie que le clic + confirmation traversent tout l'ecran
        # sans exception et sans jamais appeler `remove_unit_file`.
        manager = FakeServiceManager()
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#uninstall", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServiceScreen)
        self.assertEqual(manager.unit_files, {})

    async def test_back_button_returns_home(self):
        manager = FakeServiceManager()
        app = OmegaServApp(self._container(manager))
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_default_service_name_shown_when_nothing_persisted_yet(self):
        manager = FakeServiceManager()
        container = self._container(manager)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            self.assertEqual(pilot.app.screen.query_one("#service-name", Input).value, "omega-serv")

    async def test_renamed_service_name_persists_across_screen_visits(self):
        # Bug latent corrige (resource_status_screen.py affichait
        # toujours le statut de "omega-serv", jamais du nom reellement
        # configure ici) - verifie que le renommage est bien ecrit dans
        # settings_store (var/settings.json), pas seulement garde en
        # memoire dans le champ de saisie de cet ecran.
        manager = FakeServiceManager(known_service="mon-service-renomme")
        container = self._container(manager)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_service_screen(pilot)
            pilot.app.screen.query_one("#service-name", Input).value = "mon-service-renomme"
            await pilot.pause()
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()

            pilot.app.screen.query_one("#service", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#service-name", Input).value, "mon-service-renomme")
        self.assertEqual(container.settings_store.get("service_name"), "mon-service-renomme")


if __name__ == "__main__":
    unittest.main()
