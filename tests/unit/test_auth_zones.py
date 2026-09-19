import unittest

from omega_serv.domain.security.auth.entities import AuthZone
from omega_serv.domain.security.auth.zones import parse_auth_zones, validate_auth_zone


class TestParseAuthZones(unittest.TestCase):
    def test_parses_valid_zone(self):
        zones = parse_auth_zones([
            {"path_prefix": "/private/", "realm": "Zone privee", "allowed_users": ["admin"], "allow_methods": ["GET", "HEAD"]},
        ])
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].path_prefix, "/private/")
        self.assertEqual(zones[0].allowed_users, ("admin",))

    def test_missing_realm_defaults(self):
        zones = parse_auth_zones([{"path_prefix": "/private/", "allowed_users": ["admin"]}])
        self.assertEqual(zones[0].realm, "Zone protegee")

    def test_missing_allow_methods_defaults_to_empty(self):
        zones = parse_auth_zones([{"path_prefix": "/private/", "allowed_users": ["admin"]}])
        self.assertEqual(zones[0].allow_methods, ())


class TestValidateAuthZone(unittest.TestCase):
    def test_valid_zone_passes(self):
        zone = AuthZone(path_prefix="/private/", realm="Zone", allowed_users=("admin",))
        self.assertIsNone(validate_auth_zone(zone))

    def test_prefix_without_leading_slash_rejected(self):
        zone = AuthZone(path_prefix="private/", realm="Zone", allowed_users=("admin",))
        self.assertIsNotNone(validate_auth_zone(zone))

    def test_empty_realm_rejected(self):
        zone = AuthZone(path_prefix="/private/", realm="", allowed_users=("admin",))
        self.assertIsNotNone(validate_auth_zone(zone))

    def test_no_allowed_users_rejected(self):
        zone = AuthZone(path_prefix="/private/", realm="Zone", allowed_users=())
        self.assertIsNotNone(validate_auth_zone(zone))


if __name__ == "__main__":
    unittest.main()
