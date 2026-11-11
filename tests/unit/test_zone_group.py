"""Lot E de l'etape 3 d'omega-connect (2026-11-10) : groupe de la zone neutre donne au service par un
complement systemd, et droits partages en ligne de commande."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_lib.synchro.service_group import grants_zone_group

from omega_serv.application.services.install_service import repair_service_permissions
from omega_serv.application.services.zone_group import (
    add_zone_group,
    remove_zone_group,
    zone_group_present,
)
from omega_serv.domain.services.systemd_unit import SystemdUnitParams, generate_systemd_unit
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.services.systemd_service_manager import SystemdServiceManager
from omega_serv.ports.process_runner_port import ProcessResult


class _FakeManager:
    """Ecrit vraiment dans le dossier temporaire, comme le ferait root."""

    def __init__(self):
        self.calls = []

    def write_drop_in(self, directory, path, content):
        self.calls.append("write")
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def remove_drop_in(self, directory, path):
        self.calls.append("remove")
        path.unlink(missing_ok=True)
        if not any(directory.iterdir()):
            directory.rmdir()

    def reload_daemon(self):
        self.calls.append("reload")
        return True

    def return_root_owned(self, path, owner):
        self.calls.append(("chown", path, owner))

    def grant_directory_access(self, path, group, extra_user, private_subdirs=()):
        self.calls.append(("grant", path, group, extra_user))


class TestZoneGroup(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.units = base / "systemd"
        self.units.mkdir()
        self.project = base / "omega-serv"
        (self.project / "var").mkdir(parents=True)
        unit = generate_systemd_unit(SystemdUnitParams(
            service_name="omega-serv", description="OMEGA-SERV", python_executable=self.project / "python",
            project_root=self.project, config_path=self.project / "config" / "omega-serve.json",
            user="omega-serv", group="omega-serv"))
        (self.units / "omega-serv.service").write_text(unit, encoding="utf-8")
        self.unit_before = unit
        self.fs = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _add(self, manager, group_exists=True, root=None):
        return add_zone_group(self.fs, manager, self.units, "omega-serv", root or self.project,
                              lambda _name: group_exists)

    def test_add_then_remove_leaves_the_unit_untouched_and_no_trace(self):
        manager = _FakeManager()
        result = self._add(manager)
        self.assertTrue(result.success, result.message)
        drop_in = self.units / "omega-serv.service.d" / "omega-synchro.conf"
        self.assertTrue(grants_zone_group(drop_in.read_text(encoding="utf-8")))
        self.assertTrue(zone_group_present(self.fs, self.units, "omega-serv"))
        self.assertEqual(manager.calls, ["write", "reload"])
        self.assertEqual((self.units / "omega-serv.service").read_text(encoding="utf-8"), self.unit_before)

        result = remove_zone_group(self.fs, manager, self.units, "omega-serv")
        self.assertTrue(result.success)
        self.assertEqual(sorted(path.name for path in self.units.iterdir()), ["omega-serv.service"])

    def test_add_is_idempotent(self):
        manager = _FakeManager()
        self._add(manager)
        result = self._add(manager)
        self.assertTrue(result.success)
        self.assertEqual(manager.calls, ["write", "reload"])

    def test_refused_without_the_zone_group(self):
        manager = _FakeManager()
        result = self._add(manager, group_exists=False)
        self.assertFalse(result.success)
        self.assertEqual(manager.calls, [])

    def test_refused_for_another_installation(self):
        manager = _FakeManager()
        result = self._add(manager, root=self.project.parent / "autre")
        self.assertFalse(result.success)
        self.assertEqual(manager.calls, [])

    def test_refused_without_unit(self):
        manager = _FakeManager()
        result = add_zone_group(self.fs, manager, self.units, "omega-serv-blog", self.project, lambda _n: True)
        self.assertFalse(result.success)

    def test_remove_without_drop_in_does_nothing(self):
        manager = _FakeManager()
        result = remove_zone_group(self.fs, manager, self.units, "omega-serv")
        self.assertTrue(result.success)
        self.assertEqual(manager.calls, [])

    def test_another_drop_in_keeps_its_directory(self):
        manager = _FakeManager()
        self._add(manager)
        other = self.units / "omega-serv.service.d" / "local.conf"
        other.write_text("[Service]\nNice=5\n", encoding="utf-8")
        remove_zone_group(self.fs, manager, self.units, "omega-serv")
        self.assertTrue(other.exists())

    def test_permissions_returns_root_files_before_sharing(self):
        manager = _FakeManager()
        result = repair_service_permissions(self.fs, self.project, "omega-serv", "kraynux", manager)
        self.assertTrue(result.success)
        self.assertEqual(manager.calls[0], ("chown", self.project / "var", "kraynux"))
        self.assertEqual(manager.calls[1], ("grant", self.project / "var", "omega-serv", "kraynux"))


class _Runner:
    def __init__(self):
        self.calls = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append((list(args), input_text))
        return ProcessResult(0, "", "")

    def run_interactive(self, args):
        return 0


class TestSystemdPrivilegedCommands(unittest.TestCase):
    @patch("omega_serv.infrastructure.services.systemd_service_manager.running_as_root", return_value=True)
    def test_never_follow_links(self, _root):
        runner = _Runner()
        manager = SystemdServiceManager(runner)
        manager.return_root_owned(Path("/srv/x/var"), "kraynux")
        manager.grant_directory_access(Path("/srv/x/var"), "omega-serv", "kraynux")
        for args, _input in runner.calls:
            if "chown" in args or "chgrp" in args:
                self.assertIn("-h", args)
            if args[0] == "find" and "-exec" in args and args[args.index("-exec") + 1] in ("chown", "chgrp"):
                self.assertIn("l", args)  # ! -type l
        self.assertIn("-xdev", runner.calls[0][0])

    @patch("omega_serv.infrastructure.services.systemd_service_manager.running_as_root", return_value=True)
    def test_drop_in_commands(self, _root):
        runner = _Runner()
        manager = SystemdServiceManager(runner)
        directory = Path("/etc/systemd/system/omega-serv.service.d")
        manager.write_drop_in(directory, directory / "omega-synchro.conf", "[Service]\n")
        manager.remove_drop_in(directory, directory / "omega-synchro.conf")
        self.assertEqual([args[0] for args, _input in runner.calls], ["install", "tee", "chmod", "rm", "rmdir"])
        self.assertEqual(runner.calls[1][1], "[Service]\n")
        self.assertIn("--ignore-fail-on-non-empty", runner.calls[4][0])


if __name__ == "__main__":
    unittest.main()
