"""OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §8.5/§9 Phase E : double
minimal de ServiceManagerPort (seuls `stop`/`disable`/`remove_system_user`
sont reellement appeles par `uninstall_instance`, jamais un double
complet inutile), vraie I/O reelle pour le systeme de fichiers et le
registre (meme discipline que test_register_instance.py/
test_create_instance.py - jamais de FilesystemPort mocke)."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.instances.uninstall_instance import uninstall_instance
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.services.exceptions import ServiceControlError
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry


class _FakeServiceManager:
    def __init__(self, *, with_remove_system_user: bool = True, fail_stop: bool = False):
        self.calls: list[tuple[str, str]] = []
        self._fail_stop = fail_stop
        if with_remove_system_user:
            self.remove_system_user = self._remove_system_user  # type: ignore[method-assign]

    def stop(self, service_name: str) -> bool:
        if self._fail_stop:
            raise ServiceControlError(service_name, "stop", "echec simule", "systemd")
        self.calls.append(("stop", service_name))
        return True

    def disable(self, service_name: str) -> bool:
        self.calls.append(("disable", service_name))
        return True

    def _remove_system_user(self, user: str, group: str) -> None:
        self.calls.append(("remove-system-user", f"{user}:{group}"))


class _FailingRemoveServiceManager(_FakeServiceManager):
    """Simule un `remove_unit_file` qui echoue (sudo refuse) - jamais
    fourni par `FilesystemPort` (fallback natif), delegue explicitement
    ici pour forcer l'echec sans toucher au vrai disque."""

    def remove_unit_file(self, unit_path: Path) -> None:
        raise ServiceControlError(str(unit_path), "remove-unit-file", "sudo refuse", "systemd")


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 12, tzinfo=timezone.utc)


class TestUninstallInstance(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.unit_dir = self.root / "etc-systemd-system"
        self.unit_dir.mkdir()
        self.filesystem = LocalFilesystem()
        self.registry = JsonInstanceRegistry(self.filesystem, self.root / "instances.json")
        self.instance_dir = self.root / "omega-serv-test"
        self.instance_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _entry(self, **overrides) -> InstanceEntry:
        defaults = {
            "name": "test", "path": self.instance_dir, "bind": "127.0.0.1", "port": 8081,
            "service_name": "omega-serv-test", "created_at": datetime(2026, 9, 12, tzinfo=timezone.utc),
        }
        defaults.update(overrides)
        return InstanceEntry(**defaults)

    def _register(self, entry: InstanceEntry) -> None:
        self.registry.save([*self.registry.load(), entry])

    def test_no_unit_installed_still_removes_registry_entry(self):
        entry = self._entry()
        self._register(entry)
        result = uninstall_instance(
            self.filesystem, self.registry, _FakeServiceManager(), self.unit_dir,
            entry=entry, delete_directory=False,
        )
        self.assertTrue(result.success)
        self.assertEqual(self.registry.load(), [])
        self.assertIn("Aucune unite systemd installee", result.message)
        self.assertTrue(self.instance_dir.exists())

    def test_unit_present_stops_disables_and_removes_it(self):
        entry = self._entry()
        self._register(entry)
        unit_path = self.unit_dir / f"{entry.service_name}.service"
        unit_path.write_text(f"[Service]\nUser=omega-serv\nWorkingDirectory={entry.path}\n")
        manager = _FakeServiceManager()
        result = uninstall_instance(
            self.filesystem, self.registry, manager, self.unit_dir, entry=entry, delete_directory=False,
        )
        self.assertTrue(result.success)
        self.assertFalse(unit_path.exists())
        self.assertEqual(manager.calls[0], ("stop", "omega-serv-test"))
        self.assertEqual(manager.calls[1], ("disable", "omega-serv-test"))

    def test_removes_shared_account_when_no_other_unit_references_it(self):
        entry = self._entry()
        self._register(entry)
        unit_path = self.unit_dir / f"{entry.service_name}.service"
        unit_path.write_text(f"[Service]\nUser=omega-serv\nWorkingDirectory={entry.path}\n")
        manager = _FakeServiceManager()
        result = uninstall_instance(
            self.filesystem, self.registry, manager, self.unit_dir, entry=entry, delete_directory=False,
        )
        self.assertIn(("remove-system-user", "omega-serv:omega-serv"), manager.calls)
        self.assertIn("Compte systeme 'omega-serv' retire", result.message)

    def test_keeps_shared_account_when_another_unit_still_references_it(self):
        entry = self._entry()
        self._register(entry)
        unit_path = self.unit_dir / f"{entry.service_name}.service"
        unit_path.write_text(f"[Service]\nUser=omega-serv\nWorkingDirectory={entry.path}\n")
        (self.unit_dir / "omega-serv-prod.service").write_text(
            "[Service]\nUser=omega-serv\nWorkingDirectory=/tmp/prod\n"
        )
        manager = _FakeServiceManager()
        result = uninstall_instance(
            self.filesystem, self.registry, manager, self.unit_dir, entry=entry, delete_directory=False,
        )
        self.assertTrue(result.success)
        self.assertNotIn(("remove-system-user", "omega-serv:omega-serv"), manager.calls)
        self.assertIn("conserve", result.message)

    def test_skips_account_removal_when_manager_does_not_support_it(self):
        entry = self._entry()
        self._register(entry)
        unit_path = self.unit_dir / f"{entry.service_name}.service"
        unit_path.write_text(f"[Service]\nUser=omega-serv\nWorkingDirectory={entry.path}\n")
        manager = _FakeServiceManager(with_remove_system_user=False)
        result = uninstall_instance(
            self.filesystem, self.registry, manager, self.unit_dir, entry=entry, delete_directory=False,
        )
        self.assertTrue(result.success)  # ne plante pas sans remove_system_user

    def test_no_service_manager_skips_privileged_steps_but_still_cleans_registry(self):
        entry = self._entry()
        self._register(entry)
        unit_path = self.unit_dir / f"{entry.service_name}.service"
        unit_path.write_text(f"[Service]\nUser=omega-serv\nWorkingDirectory={entry.path}\n")
        result = uninstall_instance(
            self.filesystem, self.registry, None, self.unit_dir, entry=entry, delete_directory=False,
        )
        self.assertTrue(result.success)
        self.assertEqual(self.registry.load(), [])
        self.assertTrue(unit_path.exists())  # jamais retiree sans gestionnaire

    def test_delete_directory_true_actually_removes_it_from_disk(self):
        entry = self._entry()
        self._register(entry)
        result = uninstall_instance(
            self.filesystem, self.registry, _FakeServiceManager(), self.unit_dir,
            entry=entry, delete_directory=True,
        )
        self.assertTrue(result.success)
        self.assertFalse(self.instance_dir.exists())
        self.assertIn("supprime", result.message)

    def test_delete_directory_false_keeps_it_on_disk(self):
        entry = self._entry()
        self._register(entry)
        result = uninstall_instance(
            self.filesystem, self.registry, _FakeServiceManager(), self.unit_dir,
            entry=entry, delete_directory=False,
        )
        self.assertTrue(result.success)
        self.assertTrue(self.instance_dir.exists())
        self.assertIn("conserve", result.message)

    def test_failed_unit_removal_aborts_before_touching_registry_or_directory(self):
        entry = self._entry()
        self._register(entry)
        unit_path = self.unit_dir / f"{entry.service_name}.service"
        unit_path.write_text(f"[Service]\nUser=omega-serv\nWorkingDirectory={entry.path}\n")
        manager = _FailingRemoveServiceManager()
        result = uninstall_instance(
            self.filesystem, self.registry, manager, self.unit_dir, entry=entry, delete_directory=True,
        )
        self.assertFalse(result.success)
        self.assertEqual(len(self.registry.load()), 1)
        self.assertTrue(self.instance_dir.exists())
        self.assertTrue(unit_path.exists())


if __name__ == "__main__":
    unittest.main()
