import unittest

from omega_serv.domain.routing.zone_resolver import Zone, path_matches_prefix, resolve_zone


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


class TestPathMatchesPrefixSlashUniformity(unittest.TestCase):
    """Regression 2026-09-28 (retour utilisateur : "il y a amalgame avec
    /test/ et /test, le slash change le comportement, il faut
    uniformiser"). Avant ce correctif, path.startswith(prefix) faisait de
    "/old" et "/old/" deux prefixes distincts - "/old" sur-matchait
    "/oldish" (aucune frontiere de segment), "/old/" ne matchait pas le
    chemin exact "/old" sans slash final."""

    def test_prefix_without_slash_matches_exact_path(self):
        self.assertTrue(path_matches_prefix("/old", "/old"))

    def test_prefix_without_slash_matches_subpath(self):
        self.assertTrue(path_matches_prefix("/old/page", "/old"))

    def test_prefix_without_slash_does_not_overmatch_sibling_name(self):
        self.assertFalse(path_matches_prefix("/oldish-unrelated-page", "/old"))

    def test_prefix_with_slash_matches_exact_path_without_slash(self):
        self.assertTrue(path_matches_prefix("/old", "/old/"))

    def test_prefix_with_slash_matches_subpath(self):
        self.assertTrue(path_matches_prefix("/old/page", "/old/"))

    def test_prefix_with_or_without_slash_are_equivalent(self):
        for path in ("/old", "/old/", "/old/page"):
            self.assertEqual(
                path_matches_prefix(path, "/old"), path_matches_prefix(path, "/old/"),
            )

    def test_resolve_zone_treats_both_slash_forms_identically(self):
        without_slash = resolve_zone("/old", [Zone("/old", "a")])
        with_slash = resolve_zone("/old", [Zone("/old/", "a")])
        self.assertIsNotNone(without_slash)
        self.assertIsNotNone(with_slash)
        self.assertEqual(without_slash.data, with_slash.data)


if __name__ == "__main__":
    unittest.main()
