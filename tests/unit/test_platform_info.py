import grp
import os
import unittest
from unittest.mock import patch

from omega_serv.core.platform_info import is_missing_live_group, is_process_running, running_as_root


class TestRunningAsRoot(unittest.TestCase):
    def test_false_when_uid_nonzero(self):
        with patch("os.getuid", return_value=1000):
            self.assertFalse(running_as_root())

    def test_true_when_uid_zero(self):
        with patch("os.getuid", return_value=0):
            self.assertTrue(running_as_root())


class TestIsProcessRunning(unittest.TestCase):
    def test_true_for_the_current_process(self):
        self.assertTrue(is_process_running(os.getpid()))

    def test_false_when_process_lookup_error(self):
        with patch("os.kill", side_effect=ProcessLookupError):
            self.assertFalse(is_process_running(999999))

    def test_true_when_permission_error(self):
        with patch("os.kill", side_effect=PermissionError):
            self.assertTrue(is_process_running(1))


class TestIsMissingLiveGroup(unittest.TestCase):
    """Retour utilisateur 2026-09-13 : "gele le terminal" - cas reel
    rencontre, `usermod -aG` (grant_directory_access) n'a jamais pris
    effet pour une session deja lancee au moment de l'ajout."""

    def test_false_when_group_does_not_exist(self):
        self.assertFalse(is_missing_live_group("does-not-exist-omega-serv-test"))

    def test_false_when_group_exists_and_is_live(self):
        own_group_name = grp.getgrgid(os.getgid()).gr_name
        self.assertFalse(is_missing_live_group(own_group_name))

    def test_true_when_group_exists_but_not_live(self):
        class _FakeGrEntry:
            gr_gid = 999999  # GID improbable, jamais dans os.getgroups() reel

        with patch("grp.getgrnam", return_value=_FakeGrEntry()):
            self.assertTrue(is_missing_live_group("some-dedicated-service-group"))


if __name__ == "__main__":
    unittest.main()
