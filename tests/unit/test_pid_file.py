import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.services.pid_file import (
    pid_file_status,
    read_pid_file,
    remove_pid_file,
    write_pid_file,
)
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestPidFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "var" / "run" / "omega-serv.pid"
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_creates_parent_directories(self):
        write_pid_file(self.filesystem, self.path, 12345)
        self.assertTrue(self.path.exists())

    def test_read_after_write_round_trips(self):
        write_pid_file(self.filesystem, self.path, 12345)
        self.assertEqual(read_pid_file(self.filesystem, self.path), 12345)

    def test_read_missing_file_returns_none(self):
        self.assertIsNone(read_pid_file(self.filesystem, self.path))

    def test_read_malformed_content_returns_none(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("not-a-pid")
        self.assertIsNone(read_pid_file(self.filesystem, self.path))

    def test_remove_deletes_file(self):
        write_pid_file(self.filesystem, self.path, 12345)
        remove_pid_file(self.filesystem, self.path)
        self.assertFalse(self.path.exists())

    def test_remove_missing_file_does_not_raise(self):
        remove_pid_file(self.filesystem, self.path)

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions Unix")
    def test_read_unreadable_file_returns_none_instead_of_raising(self):
        write_pid_file(self.filesystem, self.path, 12345)
        self.path.chmod(0o000)
        try:
            self.assertIsNone(read_pid_file(self.filesystem, self.path))
        finally:
            self.path.chmod(0o600)

    def test_pid_file_status_present_and_readable(self):
        write_pid_file(self.filesystem, self.path, 12345)
        self.assertEqual(pid_file_status(self.filesystem, self.path), (12345, False))

    def test_pid_file_status_missing(self):
        self.assertEqual(pid_file_status(self.filesystem, self.path), (None, False))

    def test_pid_file_status_malformed_content(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("not-a-pid")
        self.assertEqual(pid_file_status(self.filesystem, self.path), (None, False))

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions Unix")
    def test_pid_file_status_present_but_unreadable(self):
        write_pid_file(self.filesystem, self.path, 12345)
        self.path.chmod(0o000)
        try:
            self.assertEqual(pid_file_status(self.filesystem, self.path), (None, True))
        finally:
            self.path.chmod(0o600)


if __name__ == "__main__":
    unittest.main()
