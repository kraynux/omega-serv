import unittest

from omega_serv.application.auth.manage_zones import add_zone, remove_zone
from omega_serv.domain.security.auth.entities import AuthZone


class _FakeZonesRepo:
    def __init__(self, zones=()):
        self._zones = tuple(zones)

    def load(self):
        return self._zones

    def save(self, zones):
        self._zones = tuple(zones)


class TestAddZone(unittest.TestCase):
    def test_creates_valid_zone(self):
        repo = _FakeZonesRepo()
        zone = AuthZone(path_prefix="/private/", realm="Zone", allowed_users=("admin",))
        result = add_zone(repo, zone)
        self.assertTrue(result.success)
        self.assertEqual(len(repo.load()), 1)

    def test_invalid_zone_rejected(self):
        repo = _FakeZonesRepo()
        zone = AuthZone(path_prefix="private/", realm="Zone", allowed_users=("admin",))  # pas de '/' initial
        result = add_zone(repo, zone)
        self.assertFalse(result.success)
        self.assertEqual(repo.load(), ())

    def test_duplicate_prefix_rejected(self):
        existing = AuthZone(path_prefix="/private/", realm="Zone", allowed_users=("admin",))
        repo = _FakeZonesRepo([existing])
        result = add_zone(repo, existing)
        self.assertFalse(result.success)
        self.assertEqual(len(repo.load()), 1)


class TestRemoveZone(unittest.TestCase):
    def test_removes_existing_zone(self):
        zone = AuthZone(path_prefix="/private/", realm="Zone", allowed_users=("admin",))
        repo = _FakeZonesRepo([zone])
        result = remove_zone(repo, "/private/")
        self.assertTrue(result.success)
        self.assertEqual(repo.load(), ())

    def test_missing_zone_reports_failure(self):
        repo = _FakeZonesRepo()
        result = remove_zone(repo, "/private/")
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
