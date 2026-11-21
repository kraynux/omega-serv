# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Menu Service refondu (decisions de l'auteur du 2026-11-15, projets 3.0.0 §7.6 et §7.10) : format du nom,
renommage guide sans jamais deux unites, verification en lecture seule des permissions de var/."""
from __future__ import annotations

import grp
import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.services.manage_service import ManageServiceResult
from omega_serv.application.services.rename_service import (
    plan_rename,
    rename_installed_service,
    validate_service_name,
)
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.systemd_unit import SystemdUnitParams
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.services.shared_access_probe import probe_shared_access


class TestServiceName(unittest.TestCase):
    def test_accepted(self):
        for name in ("omega-serv", "site_2", "a", "web.prod-1", "x" * 64):
            self.assertIsNone(validate_service_name(name), name)

    def test_refused(self):
        for name in ("", "Omega", "mon service", "-x", "a/b", "x" * 65, "omega-serv.service", "été"):
            self.assertIsNotNone(validate_service_name(name), name)


class _Manager:
    def __init__(self, active=True, enabled=True, fail_on=None):
        self.calls: list[tuple[str, str]] = []
        self._status = ServiceStatus("old", active=active, enabled=enabled)
        self._fail_on = fail_on

    def manager_type(self):
        return "systemd"

    def status(self, name):
        return self._status

    def _do(self, action, name):
        self.calls.append((action, name))
        if self._fail_on == action:
            from omega_serv.domain.services.exceptions import ServiceControlError
            raise ServiceControlError(name, action, "refus", "systemd")
        return True

    def start(self, name):
        return self._do("start", name)

    def stop(self, name):
        return self._do("stop", name)

    def enable(self, name):
        return self._do("enable", name)

    def disable(self, name):
        return self._do("disable", name)

    def reload_daemon(self):
        return True


class TestRename(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.root = self.base / "omega-serv"
        self.root.mkdir()
        self.units = self.base / "units"
        self.units.mkdir()
        self.fs = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _unit(self, name, directory):
        (self.units / f"{name}.service").write_text(f"[Service]\nWorkingDirectory={directory}\n")

    def _params(self, name):
        return SystemdUnitParams(service_name=name, description="d", python_executable=self.root / "python",
                                 project_root=self.root, config_path=self.root / "c.json", user="u", group="g")

    def test_plans(self):
        self.assertEqual(plan_rename(self.fs, self.units, self.root, "old", "old").kind, "same")
        self.assertEqual(plan_rename(self.fs, self.units, self.root, "old", "new").kind, "name_only")
        self._unit("old", self.root)
        self.assertEqual(plan_rename(self.fs, self.units, self.root, "old", "new").kind, "rename")
        self._unit("taken", self.base / "other")
        plan = plan_rename(self.fs, self.units, self.root, "old", "taken")
        self.assertEqual((plan.kind, plan.other_directory), ("taken", self.base / "other"))

    def test_unit_of_another_installation_under_the_old_name_is_never_renamed(self):
        self._unit("old", self.base / "other")
        self.assertEqual(plan_rename(self.fs, self.units, self.root, "old", "new").kind, "name_only")

    def test_rename_chains_and_restores_the_state(self):
        self._unit("old", self.root)
        manager = _Manager()
        plan = plan_rename(self.fs, self.units, self.root, "old", "new")
        result = rename_installed_service(self.fs, manager, self.units, plan, self._params, None)
        self.assertTrue(result.success, result.message)
        self.assertEqual(manager.calls, [("stop", "old"), ("disable", "old"), ("enable", "new"), ("start", "new")])
        self.assertFalse((self.units / "old.service").exists())
        self.assertIn("WorkingDirectory", (self.units / "new.service").read_text())
        self.assertEqual(len(result.steps), 6)

    def test_stopped_disabled_unit_is_only_moved(self):
        self._unit("old", self.root)
        manager = _Manager(active=False, enabled=False)
        plan = plan_rename(self.fs, self.units, self.root, "old", "new")
        self.assertTrue(rename_installed_service(self.fs, manager, self.units, plan, self._params, None).success)
        self.assertEqual(manager.calls, [])

    def test_failure_stops_and_says_where(self):
        self._unit("old", self.root)
        manager = _Manager(fail_on="stop")
        plan = plan_rename(self.fs, self.units, self.root, "old", "new")
        result = rename_installed_service(self.fs, manager, self.units, plan, self._params, None)
        self.assertFalse(result.success)
        self.assertIn("arrêter old", result.message)
        self.assertTrue((self.units / "old.service").exists())  # rien d'autre n'a ete fait
        self.assertFalse((self.units / "new.service").exists())
        self.assertIsInstance(ManageServiceResult(True, ""), ManageServiceResult)


class TestSharedAccessProbe(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.var = Path(self._tmp.name) / "var"
        (self.var / "run").mkdir(parents=True)
        (self.var / "backups").mkdir()
        (self.var / "backups" / "secret.tar.gz").write_text("x")
        (self.var / "run" / "a.pid").write_text("1")
        self.group = grp.getgrgid(os.getgid()).gr_name

    def tearDown(self):
        self._tmp.cleanup()

    def _share(self, path: Path):
        os.chmod(path, 0o2770 if path.is_dir() else 0o660)

    def test_missing_group(self):
        report = probe_shared_access(self.var, "groupe-qui-n-existe-pas-omega")
        self.assertFalse(report.group_exists)
        self.assertFalse(report.ok)

    def test_shared_tree_is_ok_and_backups_are_ignored(self):
        for path in (self.var, self.var / "run", self.var / "run" / "a.pid"):
            self._share(path)
        os.chmod(self.var / "backups", 0o700)  # prive : jamais exige
        report = probe_shared_access(self.var, self.group)
        self.assertTrue(report.ok, report)
        self.assertEqual(report.checked, 3)

    def test_log_archives_are_shared_and_backups_only_traversable(self):
        """Decision de l'auteur du 2026-11-17 : var/backups/logs partage (archives des journaux, administration
        web) ; var/backups seulement traversable par le groupe ; le reste de var/backups ignore."""
        logs = self.var / "backups" / "logs"
        logs.mkdir()
        (logs / "access.log.1.tar.gz").write_text("x")
        (self.var / "backups" / "config.bak").write_text("secret")
        for path in (self.var, self.var / "run", self.var / "run" / "a.pid", logs, logs / "access.log.1.tar.gz"):
            self._share(path)
        os.chown(self.var / "backups", -1, grp.getgrnam(self.group).gr_gid)
        os.chmod(self.var / "backups", 0o2710)
        os.chmod(self.var / "backups" / "config.bak", 0o600)  # prive : jamais exige
        report = probe_shared_access(self.var, self.group)
        self.assertTrue(report.ok, report)
        self.assertEqual(report.checked, 6)
        os.chmod(self.var / "backups", 0o700)  # plus traversable : le service ne voit plus les archives
        os.chmod(logs / "access.log.1.tar.gz", 0o600)
        report = probe_shared_access(self.var, self.group)
        self.assertEqual(set(report.wrong), {"var/backups", "var/backups/logs/access.log.1.tar.gz"})

    def test_unshared_entries_are_counted_and_named(self):
        self._share(self.var)
        os.chmod(self.var / "run", 0o755)  # ni ecriture de groupe ni setgid
        os.chmod(self.var / "run" / "a.pid", 0o644)
        os.symlink("/etc/passwd", self.var / "run" / "lien")  # jamais suivi
        report = probe_shared_access(self.var, self.group)
        self.assertEqual(report.wrong_count, 2)
        self.assertEqual(set(report.wrong), {"var/run", "var/run/a.pid"})


if __name__ == "__main__":
    unittest.main()
