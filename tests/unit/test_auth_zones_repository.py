import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.security.auth.entities import AuthZone
from omega_serv.domain.security.auth.exceptions import AuthZonesFileError
from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestJsonAuthZonesRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.path = self.root / "zones.json"
        self.repo = JsonAuthZonesRepository(LocalFilesystem(), self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty(self):
        self.assertEqual(self.repo.load(), ())

    def test_save_then_load_round_trips(self):
        zones = (AuthZone(path_prefix="/private/", realm="Zone privee", allowed_users=("admin",), allow_methods=("GET", "HEAD")),)
        self.repo.save(zones)
        self.assertEqual(self.repo.load(), zones)

    def test_save_sets_strict_permissions(self):
        self.repo.save((AuthZone(path_prefix="/private/", realm="Zone", allowed_users=("admin",)),))
        self.assertEqual(LocalFilesystem().file_mode(self.path), 0o600)

    def test_invalid_json_raises(self):
        self.path.write_text("{ not json")
        with self.assertRaises(AuthZonesFileError):
            self.repo.load()

    def test_unsupported_version_raises(self):
        self.path.write_text('{"version": 99, "zones": []}')
        with self.assertRaises(AuthZonesFileError):
            self.repo.load()


if __name__ == "__main__":
    unittest.main()
