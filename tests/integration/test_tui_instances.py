# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration multi-instance (OMEGA-SERV_PLAN-DETAILLE_
MULTI_INSTANCE.md, Phases A/B/C) : bannière d'instance (`sub_title`),
label conditionnel du menu principal, ecran Instances (liste + statut),
et flux de creation. `create_instance_runner` double en memoire pour
les tests d'orchestration UI (le pipeline REEL - venv/pip - est deja
verifie par tests/unit/test_create_instance.py::TestCreateInstanceRealVenv,
jamais redouble ici, trop lent pour un test d'ecran).

Registre TOUJOURS isole (`instance_registry_path` injecte, jamais le
vrai `~/.config/omega-serv/instances.json`) - meme discipline que
`systemd_unit_dir` dans test_tui_service.py."""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from textual.widgets import Button, DataTable, Input, Static

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.pending_instance_switch import PendingInstanceSwitch
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.create_instance_progress_screen import (
    CreateInstanceProgressScreen,
)
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.instances_screen import InstancesScreen
from omega_serv.interfaces.tui.screens.service_screen import ServiceScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from tests.integration.test_tui_service import FakeServiceManager

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _UninstallCapableServiceManager:
    """Fake minimal pour le flux de desinstallation complete (Phase E) -
    contrairement a FakeServiceManager (test_tui_service.py, dont
    remove_unit_file suit un dict EN MEMOIRE), n'implemente pas
    remove_unit_file : le retrait de l'unite delegue donc au fallback
    reel de FilesystemPort, necessaire pour que
    `check_account_still_in_use` (qui relit le VRAI repertoire
    d'unites sur disque) observe un etat coherent apres suppression."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def manager_type(self) -> str:
        return "systemd"

    def status(self, service_name: str) -> ServiceStatus:
        # `_refresh_table()` interroge le statut de CHAQUE entree du
        # registre inconditionnellement - meme un fake volontairement
        # minimal doit repondre, sinon le simple affichage de l'ecran
        # plante avant meme d'atteindre le flux de desinstallation.
        return ServiceStatus(service_name=service_name, active=False, enabled=False)

    def stop(self, service_name: str) -> bool:
        self.calls.append(("stop", service_name))
        return True

    def disable(self, service_name: str) -> bool:
        self.calls.append(("disable", service_name))
        return True

    def remove_system_user(self, user: str, group: str) -> None:
        self.calls.append(("remove-system-user", f"{user}:{group}"))


def _entry(**overrides) -> InstanceEntry:
    defaults = {
        "name": "prod", "path": Path("/tmp/does-not-matter"), "bind": "127.0.0.1", "port": 8080,
        "service_name": "omega-serv", "created_at": datetime(2026, 9, 11, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return InstanceEntry(**defaults)


class TestTuiInstances(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.registry_path = self.root.parent / f"{self.root.name}-instances.json"
        self.addCleanup(self.registry_path.unlink, missing_ok=True)
        # Repertoire d'unites systemd FACTICE (Phase E) - meme discipline
        # que test_tui_service.py, jamais le vrai /etc/systemd/system/.
        self.unit_dir = self.root.parent / f"{self.root.name}-etc-systemd-system"
        self.unit_dir.mkdir()
        self.addCleanup(shutil.rmtree, self.unit_dir, ignore_errors=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, **kwargs) -> DependencyContainer:
        return DependencyContainer(project_root=self.root, instance_registry_path=self.registry_path, **kwargs)

    def _other_instance_dir(self, *, with_venv: bool) -> Path:
        other = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        if with_venv:
            (other / ".venv" / "bin").mkdir(parents=True)
            (other / ".venv" / "bin" / "python").touch()
        return other

    async def _reach_home(self, pilot):
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_instances_button_shows_generic_label_when_zero_or_one_known(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            button = pilot.app.screen.query_one("#instances", Button)
            self.assertEqual(str(button.label), "MULTI-INSTANCE")

    async def test_instances_button_label_reflects_count_when_two_or_more_known(self):
        container = self._container()
        container.instance_registry.save([_entry(name="prod"), _entry(name="test", port=8081)])
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            button = pilot.app.screen.query_one("#instances", Button)
            self.assertEqual(str(button.label), "INSTANCES (2)")

    async def test_sub_title_shows_instance_suffix_only_with_two_or_more(self):
        container = self._container()
        container.instance_registry.save([_entry(name="prod"), _entry(name="test", port=8081)])
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            self.assertIn(f"Instance : {self.root.name}", pilot.app.sub_title)

    async def test_sub_title_has_no_suffix_for_a_single_known_instance(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            self.assertNotIn("Instance :", pilot.app.sub_title)

    async def test_service_screen_directory_hint_only_with_two_or_more(self):
        container = self._container(service_manager_factory=lambda: FakeServiceManager())
        container.instance_registry.save([_entry(name="prod"), _entry(name="test", port=8081)])
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            pilot.app.screen.query_one("#service", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServiceScreen)
            self.assertTrue(any(
                "Repertoire pilote" in str(w.render())
                for w in pilot.app.screen.query(Static) if w.id is None
            ))

    async def _open_instances(self, pilot):
        pilot.app.screen.query_one("#instances", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, InstancesScreen)

    async def test_instances_screen_lists_registered_entries_with_status(self):
        manager = FakeServiceManager(known_service="omega-serv")
        manager.start("omega-serv")
        container = self._container(service_manager_factory=lambda: manager)
        container.instance_registry.save([_entry(name="prod", path=self.root, service_name="omega-serv")])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            table = pilot.app.screen.query_one("#instances-table", DataTable)
            self.assertEqual(table.row_count, 1)
            row = list(table.get_row_at(0))
            self.assertIn("prod", row[0])
            self.assertIn("(courante)", row[0])
            self.assertEqual(row[4], "actif")

    async def test_back_button_returns_home(self):
        container = self._container()
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def test_create_instance_success_registers_and_refreshes_table(self):
        created = {}

        def fake_runner(source_root, name, target_parent_dir, bind, port, service_name, filesystem, registry, clock, on_step):
            created["args"] = (name, target_parent_dir, bind, port, service_name)
            on_step(1, 6, "Validation des parametres")
            on_step(6, 6, "Enregistrement dans le registre")
            registry.save([*registry.load(), _entry(
                name=name, path=target_parent_dir / name, bind=bind, port=port,
                service_name=service_name, created_at=clock.now(),
            )])

        container = self._container(create_instance_runner=fake_runner)
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-name", Input).value = "test-instance"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, CreateInstanceProgressScreen)

            for _ in range(20):
                await pilot.pause()
                if not pilot.app.screen.query_one("#close", Button).disabled:
                    break
                await asyncio.sleep(0.05)
            else:
                self.fail("la creation d'instance ne s'est jamais terminee")

            self.assertIn("succes", str(pilot.app.screen.query_one("#progress-result", Static).render()))
            pilot.app.screen.query_one("#close", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, InstancesScreen)
            table = pilot.app.screen.query_one("#instances-table", DataTable)
            self.assertEqual(table.row_count, 1)
        self.assertEqual(created["args"][0], "test-instance")

    async def test_create_instance_failure_shows_error_without_registering(self):
        def failing_runner(source_root, name, target_parent_dir, bind, port, service_name, filesystem, registry, clock, on_step):
            on_step(1, 6, "Validation des parametres")
            return "erreur simulee"

        container = self._container(create_instance_runner=failing_runner)
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-name", Input).value = "test-instance"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()

            for _ in range(20):
                await pilot.pause()
                if not pilot.app.screen.query_one("#close", Button).disabled:
                    break
                await asyncio.sleep(0.05)
            else:
                self.fail("la creation d'instance ne s'est jamais terminee")

            self.assertIn("erreur simulee", str(pilot.app.screen.query_one("#progress-result", Static).render()))
        self.assertEqual(container.instance_registry.load(), [])

    async def test_empty_name_rejected_before_pushing_progress_screen(self):
        container = self._container(create_instance_runner=lambda *a, **k: None)
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            pilot.app.screen.query_one("#create", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-name", Input).value = ""
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, InstancesScreen)

    async def _select_row(self, pilot, index: int) -> None:
        table = pilot.app.screen.query_one("#instances-table", DataTable)
        table.move_cursor(row=index)
        await pilot.pause()
        table.action_select_cursor()
        await pilot.pause()

    async def test_switch_button_disabled_before_any_selection(self):
        other = self._other_instance_dir(with_venv=True)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            self.assertTrue(pilot.app.screen.query_one("#switch-to", Button).disabled)

    async def test_switch_button_stays_disabled_for_current_instance_row(self):
        other = self._other_instance_dir(with_venv=True)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 0)
            self.assertTrue(pilot.app.screen.query_one("#switch-to", Button).disabled)

    async def test_switch_button_enabled_for_another_instance_row(self):
        other = self._other_instance_dir(with_venv=True)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            self.assertFalse(pilot.app.screen.query_one("#switch-to", Button).disabled)

    async def test_switch_confirmation_shows_target_name_and_path(self):
        other = self._other_instance_dir(with_venv=True)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#switch-to", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            texts = "\n".join(str(w.render()) for w in pilot.app.screen.query(Static))
            self.assertIn("'test'", texts)
            self.assertIn(str(other), texts)

    async def test_switch_cancelled_keeps_app_running_and_pending_switch_unset(self):
        other = self._other_instance_dir(with_venv=True)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#switch-to", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, InstancesScreen)
            self.assertTrue(app.is_running)
            self.assertIsNone(app.pending_switch)

    async def test_switch_confirmed_with_missing_venv_shows_error_and_stays_open(self):
        other = self._other_instance_dir(with_venv=False)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#switch-to", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, InstancesScreen)
            self.assertTrue(app.is_running)
            self.assertIsNone(app.pending_switch)

    async def test_switch_confirmed_with_existing_venv_sets_pending_switch_and_exits(self):
        other = self._other_instance_dir(with_venv=True)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#switch-to", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
        self.assertFalse(app.is_running)
        self.assertEqual(
            app.pending_switch,
            PendingInstanceSwitch(python_executable=other / ".venv" / "bin" / "python", source_name="prod"),
        )

    async def test_uninstall_button_disabled_before_any_selection(self):
        other = self._other_instance_dir(with_venv=False)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            self.assertTrue(pilot.app.screen.query_one("#uninstall-instance", Button).disabled)

    async def test_uninstall_button_stays_disabled_for_current_instance_row(self):
        other = self._other_instance_dir(with_venv=False)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 0)
            self.assertTrue(pilot.app.screen.query_one("#uninstall-instance", Button).disabled)

    async def test_uninstall_button_enabled_for_another_instance_row(self):
        other = self._other_instance_dir(with_venv=False)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            self.assertFalse(pilot.app.screen.query_one("#uninstall-instance", Button).disabled)

    async def test_uninstall_cancelling_first_confirmation_changes_nothing(self):
        other = self._other_instance_dir(with_venv=False)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root), _entry(name="test", path=other, port=8081),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#uninstall-instance", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, InstancesScreen)
        self.assertEqual(len(container.instance_registry.load()), 2)
        self.assertTrue(other.exists())

    async def test_uninstall_confirmed_but_directory_kept(self):
        other = self._other_instance_dir(with_venv=False)
        container = self._container()
        container.instance_registry.save([
            _entry(name="prod", path=self.root),
            _entry(name="test", path=other, port=8081, service_name="omega-serv-test"),
        ])
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#uninstall-instance", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, InstancesScreen)
            table = pilot.app.screen.query_one("#instances-table", DataTable)
            self.assertEqual(table.row_count, 1)
        self.assertEqual(len(container.instance_registry.load()), 1)
        self.assertTrue(other.exists())

    async def test_uninstall_confirmed_removes_unit_account_registry_and_directory(self):
        other = self._other_instance_dir(with_venv=False)
        manager = _UninstallCapableServiceManager()
        container = self._container(
            service_manager_factory=lambda: manager, systemd_unit_dir=self.unit_dir,
        )
        container.instance_registry.save([
            _entry(name="prod", path=self.root),
            _entry(name="test", path=other, port=8081, service_name="omega-serv-test"),
        ])
        unit_path = self.unit_dir / "omega-serv-test.service"
        unit_path.write_text(f"[Service]\nUser=omega-serv\nWorkingDirectory={other}\n")
        app = OmegaServApp(container)
        async with app.run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#uninstall-instance", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, InstancesScreen)
            table = pilot.app.screen.query_one("#instances-table", DataTable)
            self.assertEqual(table.row_count, 1)
        self.assertEqual(len(container.instance_registry.load()), 1)
        self.assertFalse(other.exists())
        self.assertFalse(unit_path.exists())
        self.assertIn(("stop", "omega-serv-test"), manager.calls)
        self.assertIn(("disable", "omega-serv-test"), manager.calls)
        self.assertIn(("remove-system-user", "omega-serv:omega-serv"), manager.calls)


if __name__ == "__main__":
    unittest.main()
