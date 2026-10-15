import tempfile
import unittest
from pathlib import Path

from omega_serv.application.logs.library import (
    add_many_to_library,
    add_to_library,
    list_library,
    refresh_log_file,
    remove_from_library,
)
from omega_serv.domain.logs.library import LogFile
from omega_serv.infrastructure.logging.json_log_library_repository import JsonLogLibraryRepository


class TestRefreshLogFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_existing_file_reports_size_and_mtime(self):
        path = self.root / "a.log"
        path.write_text("hello")
        result = refresh_log_file(str(path))
        self.assertTrue(result.exists)
        self.assertEqual(result.size_bytes, 5)
        self.assertIsNotNone(result.modified_at)

    def test_missing_file_reports_absent(self):
        result = refresh_log_file(str(self.root / "missing.log"))
        self.assertFalse(result.exists)
        self.assertIsNone(result.size_bytes)

    def test_empty_file_is_stale(self):
        path = self.root / "empty.log"
        path.write_text("")
        result = refresh_log_file(str(path))
        self.assertTrue(result.is_stale)


class TestLibraryUseCases(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repository = JsonLogLibraryRepository(self.root / "library.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_add_then_list_round_trips(self):
        add_to_library(self.repository, LogFile(path="/var/log/a.log", access="file"))
        entries = list_library(self.repository)
        self.assertEqual([e.path for e in entries], ["/var/log/a.log"])

    def test_adding_same_path_twice_does_not_duplicate(self):
        add_to_library(self.repository, LogFile(path="/var/log/a.log"))
        add_to_library(self.repository, LogFile(path="/var/log/a.log"))
        self.assertEqual(len(list_library(self.repository)), 1)

    def test_add_many_returns_count(self):
        count = add_many_to_library(self.repository, [
            LogFile(path="/var/log/a.log"), LogFile(path="/var/log/b.log"),
        ])
        self.assertEqual(count, 2)
        self.assertEqual(len(list_library(self.repository)), 2)

    def test_remove_from_library(self):
        add_to_library(self.repository, LogFile(path="/var/log/a.log"))
        remove_from_library(self.repository, "/var/log/a.log")
        self.assertEqual(list_library(self.repository), [])

    def test_list_reflects_real_disk_state_not_stale_add_time_data(self):
        path = self.root / "real.log"
        add_to_library(self.repository, LogFile(path=str(path)))
        self.assertFalse(list_library(self.repository)[0].exists)
        path.write_text("now it exists")
        self.assertTrue(list_library(self.repository)[0].exists)


if __name__ == "__main__":
    unittest.main()
