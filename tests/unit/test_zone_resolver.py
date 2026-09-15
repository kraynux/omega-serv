# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone


class TestResolveZone(unittest.TestCase):
    def test_no_match_returns_none(self):
        self.assertIsNone(resolve_zone("/public/x", [Zone("/admin/", "a")]))

    def test_single_match(self):
        zone = resolve_zone("/admin/panel", [Zone("/admin/", "a")])
        self.assertEqual(zone.data, "a")

    def test_longest_prefix_wins(self):
        zones = [Zone("/admin/", "generic"), Zone("/admin/panel/", "specific")]
        zone = resolve_zone("/admin/panel/settings", zones)
        self.assertEqual(zone.data, "specific")

    def test_root_prefix_matches_everything(self):
        zone = resolve_zone("/anything/at/all", [Zone("/", "root")])
        self.assertEqual(zone.data, "root")


if __name__ == "__main__":
    unittest.main()
