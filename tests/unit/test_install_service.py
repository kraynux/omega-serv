# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.services.install_service import (
    check_account_still_in_use,
    check_for_conflicting_unit,
    check_for_name_hijack,
    install_systemd_service,
    uninstall_systemd_service,
)
from omega_serv.domain.services.systemd_unit import SystemdUnitParams
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeServiceManager:
    def __init__(self, has_reload=True):
        self.reload_calls = 0
        if has_reload:
            self.reload_daemon = self._reload_daemon

    def _reload_daemon(self):
        self.reload_calls += 1
        return True


class _FakePrivilegedServiceManager:
    """Simule un gestionnaire qui expose write_unit_file/remove_unit_file
    (plan interface §3.6, 2026-09-08) - l'ecriture ne doit alors JAMAIS
    passer par FilesystemPort."""

    def __init__(self):
        self.write_calls = []
        self.remove_calls = []

    def write_unit_file(self, unit_path, content):
        self.write_calls.append((unit_path, content))

    def remove_unit_file(self, unit_path):
        self.remove_calls.append(unit_path)


class _FakeServiceManagerWithUserCreation(_FakeServiceManager):
    def __init__(self):
        super().__init__()
        self.create_user_calls = []

    def create_system_user(self, user, group):
        self.create_user_calls.append((user, group))


class _FakeServiceManagerWithDirectoryAccess(_FakeServiceManagerWithUserCreation):
    def __init__(self):
        super().__init__()
        self.grant_directory_access_calls = []

    def grant_directory_access(self, path, group, extra_user):
        self.grant_directory_access_calls.append((path, group, extra_user))


class TestInstallSystemdService(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.unit_path = self.root / "omega-serv.service"

    def tearDown(self):
        self._tmp.cleanup()

    def _params(self):
        return SystemdUnitParams(
            service_name="omega-serv", description="OMEGA-SERV", python_executable=self.root / "python",
            project_root=self.root, config_path=self.root / "config" / "omega-serve.json",
            user="omega-serv", group="omega-serv",
        )

    def test_install_writes_unit_file(self):
        manager = _FakeServiceManager()
        result = install_systemd_service(self.filesystem, self._params(), self.unit_path, manager)
        self.assertTrue(result.success)
        self.assertTrue(self.unit_path.exists())
        self.assertIn("NoNewPrivileges=true", self.unit_path.read_text())

    def test_install_calls_reload_daemon_when_available(self):
        manager = _FakeServiceManager(has_reload=True)
        install_systemd_service(self.filesystem, self._params(), self.unit_path, manager)
        self.assertEqual(manager.reload_calls, 1)

    def test_install_does_not_crash_without_reload_daemon(self):
        manager = _FakeServiceManager(has_reload=False)
        result = install_systemd_service(self.filesystem, self._params(), self.unit_path, manager)
        self.assertTrue(result.success)

    def test_install_creates_system_user_when_available(self):
        # Retour utilisateur 2026-09-10, vrai bug trouve : l'unite
        # referencait toujours User=/Group= dedies sans que rien ne les
        # cree - le service echouait systematiquement au demarrage.
        manager = _FakeServiceManagerWithUserCreation()
        result = install_systemd_service(self.filesystem, self._params(), self.unit_path, manager)
        self.assertTrue(result.success)
        self.assertEqual(manager.create_user_calls, [("omega-serv", "omega-serv")])
        self.assertIn("compte systeme", result.message)

    def test_install_does_not_crash_without_create_system_user(self):
        manager = _FakeServiceManager()  # n'implemente pas create_system_user
        result = install_systemd_service(self.filesystem, self._params(), self.unit_path, manager)
        self.assertTrue(result.success)

    def test_install_grants_directory_access_when_available_and_user_given(self):
        # Retour utilisateur 2026-09-10, second vrai bug trouve juste
        # apres le premier : le compte systeme cree n'avait toujours
        # aucun droit d'ecriture sur var/ (le service crash-loopait,
        # PermissionError sur le fichier PID selon journalctl).
        manager = _FakeServiceManagerWithDirectoryAccess()
        result = install_systemd_service(
            self.filesystem, self._params(), self.unit_path, manager, installing_user="kraynux",
        )
        self.assertTrue(result.success)
        self.assertEqual(
            manager.grant_directory_access_calls,
            [(self.root / "var", "omega-serv", "kraynux")],
        )
        self.assertIn("kraynux", result.message)
        self.assertIn("omega-serv", result.message)

    def test_install_does_not_grant_directory_access_without_installing_user(self):
        manager = _FakeServiceManagerWithDirectoryAccess()
        result = install_systemd_service(self.filesystem, self._params(), self.unit_path, manager)
        self.assertTrue(result.success)
        self.assertEqual(manager.grant_directory_access_calls, [])

    def test_install_does_not_crash_without_grant_directory_access(self):
        manager = _FakeServiceManagerWithUserCreation()  # n'implemente pas grant_directory_access
        result = install_systemd_service(
            self.filesystem, self._params(), self.unit_path, manager, installing_user="kraynux",
        )
        self.assertTrue(result.success)

    def test_uninstall_removes_unit_file(self):
        self.unit_path.write_text("dummy unit content")
        manager = _FakeServiceManager()
        result = uninstall_systemd_service(self.filesystem, self.unit_path, manager)
        self.assertTrue(result.success)
        self.assertFalse(self.unit_path.exists())

    def test_uninstall_missing_unit_reports_failure(self):
        manager = _FakeServiceManager()
        result = uninstall_systemd_service(self.filesystem, self.unit_path, manager)
        self.assertFalse(result.success)

    def test_install_delegates_to_write_unit_file_when_available(self):
        manager = _FakePrivilegedServiceManager()
        result = install_systemd_service(self.filesystem, self._params(), self.unit_path, manager)
        self.assertTrue(result.success)
        self.assertEqual(len(manager.write_calls), 1)
        self.assertEqual(manager.write_calls[0][0], self.unit_path)
        self.assertIn("NoNewPrivileges=true", manager.write_calls[0][1])
        # Jamais ecrit via FilesystemPort quand write_unit_file existe -
        # /etc/systemd/system/ echappe au perimetre projet, ecrire quand
        # meme via FilesystemPort echouerait reellement sans elevation.
        self.assertFalse(self.unit_path.exists())

    def test_uninstall_delegates_to_remove_unit_file_when_available(self):
        self.unit_path.write_text("dummy unit content")
        manager = _FakePrivilegedServiceManager()
        result = uninstall_systemd_service(self.filesystem, self.unit_path, manager)
        self.assertTrue(result.success)
        self.assertEqual(manager.remove_calls, [self.unit_path])
        # remove_unit_file (fake) ne supprime rien reellement ici - la
        # verification est que install_service delegue bien l'appel,
        # pas que le fichier disparait (verifie separement cote
        # systemd_service_manager.py::remove_unit_file lui-meme).


class TestCheckForConflictingUnit(unittest.TestCase):
    """Retour utilisateur 2026-09-10 : garde-fou minimal avant
    d'installer une unite - detecte une AUTRE unite deja installee
    pointant vers le meme repertoire projet. I/O reelle sur un
    repertoire temporaire (meme discipline que le reste de ce fichier -
    jamais de FilesystemPort mocke)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.unit_dir = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.project_root = Path("/home/kraynux/DEV/SERV/omega-serv")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_unit(self, name: str, working_directory: Path) -> None:
        (self.unit_dir / name).write_text(f"[Service]\nWorkingDirectory={working_directory}\n")

    def test_detects_other_unit_on_same_directory(self):
        self._write_unit("omega-serv.service", self.project_root)
        conflict = check_for_conflicting_unit(self.filesystem, self.unit_dir, self.project_root, "omega-serv-2")
        self.assertEqual(conflict, "omega-serv")

    def test_no_conflict_when_reinstalling_same_name(self):
        self._write_unit("omega-serv.service", self.project_root)
        self.assertIsNone(check_for_conflicting_unit(self.filesystem, self.unit_dir, self.project_root, "omega-serv"))

    def test_no_conflict_for_unrelated_unit(self):
        self._write_unit("sshd.service", Path("/etc/ssh"))
        self.assertIsNone(check_for_conflicting_unit(self.filesystem, self.unit_dir, self.project_root, "omega-serv"))

    def test_no_conflict_when_unit_dir_missing(self):
        missing = self.unit_dir / "does-not-exist"
        self.assertIsNone(check_for_conflicting_unit(self.filesystem, missing, self.project_root, "omega-serv"))

    def test_ignores_non_service_files(self):
        (self.unit_dir / "README.txt").write_text(f"WorkingDirectory={self.project_root}\n")
        self.assertIsNone(check_for_conflicting_unit(self.filesystem, self.unit_dir, self.project_root, "omega-serv"))


class TestCheckForNameHijack(unittest.TestCase):
    """Sens inverse de TestCheckForConflictingUnit, meme retour
    utilisateur 2026-09-10 : deux repertoires DIFFERENTS utilisant le
    meme nom de service par defaut ("omega-serv") - non couvert par le
    garde-fou precedent, `write_unit_file` (sudo tee) ecraserait
    silencieusement l'unite de l'autre installation sans avertir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.unit_dir = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.project_root = Path("/home/kraynux/DEV/SERV/omega-serv")
        self.other_root = Path("/home/kraynux/DEV/SERV2/omega-serv")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_unit(self, name: str, working_directory: Path) -> None:
        (self.unit_dir / name).write_text(f"[Service]\nWorkingDirectory={working_directory}\n")

    def test_detects_name_already_used_by_another_directory(self):
        self._write_unit("omega-serv.service", self.other_root)
        hijack = check_for_name_hijack(self.filesystem, self.unit_dir, self.project_root, "omega-serv")
        self.assertEqual(hijack, self.other_root)

    def test_no_hijack_when_reinstalling_same_directory(self):
        self._write_unit("omega-serv.service", self.project_root)
        self.assertIsNone(check_for_name_hijack(self.filesystem, self.unit_dir, self.project_root, "omega-serv"))

    def test_no_hijack_when_name_never_installed(self):
        self.assertIsNone(check_for_name_hijack(self.filesystem, self.unit_dir, self.project_root, "omega-serv"))

    def test_no_hijack_when_unit_dir_missing(self):
        missing = self.unit_dir / "does-not-exist"
        self.assertIsNone(check_for_name_hijack(self.filesystem, missing, self.project_root, "omega-serv"))


class TestCheckAccountStillInUse(unittest.TestCase):
    """OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §8.1/§9 Phase E : le
    compte systeme dedie est IDENTIQUE pour toutes les instances -
    avant de le supprimer a la desinstallation d'une instance, verifier
    qu'aucune AUTRE unite installee ne le reference encore. I/O reelle
    (meme discipline que TestCheckForConflictingUnit/TestCheckForNameHijack
    ci-dessus)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.unit_dir = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _write_unit(self, name: str, user: str) -> None:
        (self.unit_dir / name).write_text(f"[Service]\nUser={user}\nWorkingDirectory=/tmp/x\n")

    def test_detects_another_unit_still_using_the_account(self):
        self._write_unit("omega-serv-test.service", "omega-serv")
        self._write_unit("omega-serv-prod.service", "omega-serv")
        still_used = check_account_still_in_use(self.filesystem, self.unit_dir, "omega-serv", "omega-serv-test")
        self.assertEqual(still_used, "omega-serv-prod")

    def test_no_other_use_when_only_the_excluded_unit_references_it(self):
        self._write_unit("omega-serv-test.service", "omega-serv")
        self.assertIsNone(check_account_still_in_use(self.filesystem, self.unit_dir, "omega-serv", "omega-serv-test"))

    def test_no_other_use_when_unit_dir_missing(self):
        missing = self.unit_dir / "does-not-exist"
        self.assertIsNone(check_account_still_in_use(self.filesystem, missing, "omega-serv", "omega-serv-test"))


if __name__ == "__main__":
    unittest.main()
