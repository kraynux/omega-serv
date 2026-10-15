import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.logs.library import LibraryRecord
from omega_serv.infrastructure.logging.json_log_library_repository import JsonLogLibraryRepository


class TestJsonLogLibraryRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "sub" / "library.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_all_on_missing_file_is_empty(self):
        self.assertEqual(JsonLogLibraryRepository(self.path).list_all(), [])

    def test_add_creates_parent_directory(self):
        repo = JsonLogLibraryRepository(self.path)
        repo.add(LibraryRecord(path="/var/log/a.log"))
        self.assertTrue(self.path.exists())

    def test_survives_a_fresh_instance_round_trip(self):
        JsonLogLibraryRepository(self.path).add(LibraryRecord(path="/var/log/a.log", service_id="svc"))
        reloaded = JsonLogLibraryRepository(self.path).list_all()
        self.assertEqual(reloaded, [LibraryRecord(path="/var/log/a.log", service_id="svc")])

    def test_add_same_path_replaces_not_duplicates(self):
        repo = JsonLogLibraryRepository(self.path)
        repo.add(LibraryRecord(path="/a.log", service_id="old"))
        repo.add(LibraryRecord(path="/a.log", service_id="new"))
        entries = repo.list_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].service_id, "new")

    def test_contains(self):
        repo = JsonLogLibraryRepository(self.path)
        repo.add(LibraryRecord(path="/a.log"))
        self.assertTrue(repo.contains("/a.log"))
        self.assertFalse(repo.contains("/b.log"))

    def test_remove(self):
        repo = JsonLogLibraryRepository(self.path)
        repo.add(LibraryRecord(path="/a.log"))
        repo.remove("/a.log")
        self.assertEqual(repo.list_all(), [])


if __name__ == "__main__":
    unittest.main()
