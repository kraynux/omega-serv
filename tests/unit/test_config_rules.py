import unittest

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.rules import (
    detect_conflicts,
    detect_zone_prefix_overlaps,
    has_blocking_conflicts,
)


class TestDetectConflicts(unittest.TestCase):
    def test_default_config_has_no_conflicts(self):
        self.assertEqual(detect_conflicts(OmegaServConfig()), [])

    def test_trusted_proxy_without_networks_is_a_conflict(self):
        config = OmegaServConfig.from_dict({"options": {"trusted_proxy": {"enabled": True}}})
        conflicts = detect_conflicts(config)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].severity, "error")

    def test_trusted_proxy_with_networks_is_fine(self):
        config = OmegaServConfig.from_dict({
            "options": {"trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"]}},
        })
        self.assertEqual(detect_conflicts(config), [])

    def test_trusted_proxy_disabled_is_never_a_conflict(self):
        config = OmegaServConfig.from_dict({"options": {"trusted_proxy": {"enabled": False}}})
        self.assertEqual(detect_conflicts(config), [])


class TestDetectZonePrefixOverlaps(unittest.TestCase):
    @staticmethod
    def _config(**options):
        return OmegaServConfig.from_dict({"options": options})

    def test_no_zones_configured_has_no_overlap(self):
        self.assertEqual(detect_zone_prefix_overlaps(OmegaServConfig()), [])

    def test_disjoint_prefixes_different_types_no_overlap(self):
        config = self._config(
            aliases={"enabled": True, "list": [{"url_prefix": "/static/", "target_path": "assets"}]},
            reverse_proxy={"enabled": True, "zones": [
                {"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]},
            ]},
        )
        self.assertEqual(detect_zone_prefix_overlaps(config), [])

    def test_same_type_overlap_is_not_reported(self):
        """Deux zones du MEME type qui se chevauchent sont deja gerees
        par resolve_zone (plus-long-prefixe-gagne, comportement voulu) -
        hors scope de cette detection (§29.4 : uniquement entre TYPES
        differents)."""
        config = self._config(aliases={"enabled": True, "list": [
            {"url_prefix": "/api/", "target_path": "a"},
            {"url_prefix": "/api/v2/", "target_path": "b"},
        ]})
        self.assertEqual(detect_zone_prefix_overlaps(config), [])

    def test_disabled_option_is_ignored(self):
        config = self._config(
            aliases={"enabled": False, "list": [{"url_prefix": "/api/", "target_path": "a"}]},
            reverse_proxy={"enabled": True, "zones": [
                {"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]},
            ]},
        )
        self.assertEqual(detect_zone_prefix_overlaps(config), [])

    def test_alias_shadows_reverse_proxy_is_reported_as_warning(self):
        config = self._config(
            aliases={"enabled": True, "list": [{"url_prefix": "/api/", "target_path": "a"}]},
            reverse_proxy={"enabled": True, "zones": [
                {"url_prefix": "/api/v2/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]},
            ]},
        )
        conflicts = detect_zone_prefix_overlaps(config)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].severity, "warning")
        self.assertIn("options.alias", conflicts[0].message)
        self.assertIn("l'emporte toujours", conflicts[0].message)

    def test_dispatch_order_names_the_correct_winner_regardless_of_prefix_length(self):
        """Le prefixe le PLUS COURT (alias, etape plus tot dans le
        pipeline) l'emporte ici sur le prefixe le plus LONG (reverse
        proxy, etape plus tard) - l'inverse de resolve_zone au sein d'un
        meme type. Le message doit nommer alias comme gagnant, jamais
        se tromper en supposant "plus long prefixe gagne" entre types."""
        config = self._config(
            reverse_proxy={"enabled": True, "zones": [
                {"url_prefix": "/api/v2/admin/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]},
            ]},
            aliases={"enabled": True, "list": [{"url_prefix": "/api/", "target_path": "a"}]},
        )
        conflicts = detect_zone_prefix_overlaps(config)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("options.alias ('/api/')", conflicts[0].message)
        self.assertIn("l'emporte toujours", conflicts[0].message)

    def test_redirect_wins_over_alias_per_pipeline_order(self):
        config = self._config(
            redirects={"enabled": True, "list": [{"url_prefix": "/old/", "destination": "/new/"}]},
            aliases={"enabled": True, "list": [{"url_prefix": "/old/sub/", "target_path": "a"}]},
        )
        conflicts = detect_zone_prefix_overlaps(config)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("options.redirects ('/old/')", conflicts[0].message)

    def test_exact_same_prefix_across_types_is_reported(self):
        config = self._config(
            aliases={"enabled": True, "list": [{"url_prefix": "/app/", "target_path": "a"}]},
            fastcgi={"enabled": True, "url_prefix": "/app/", "script_root": "php"},
        )
        conflicts = detect_zone_prefix_overlaps(config)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("options.alias ('/app/')", conflicts[0].message)

    def test_detect_conflicts_combines_trusted_proxy_error_and_zone_overlap_warning(self):
        config = OmegaServConfig.from_dict({"options": {
            "trusted_proxy": {"enabled": True},
            "aliases": {"enabled": True, "list": [{"url_prefix": "/api/", "target_path": "a"}]},
            "reverse_proxy": {"enabled": True, "zones": [
                {"url_prefix": "/api/v2/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]},
            ]},
        }})
        conflicts = detect_conflicts(config)
        self.assertEqual(len(conflicts), 2)
        self.assertTrue(has_blocking_conflicts(conflicts))
        severities = {c.severity for c in conflicts}
        self.assertEqual(severities, {"error", "warning"})


class TestHasBlockingConflicts(unittest.TestCase):
    def test_empty_list_is_not_blocking(self):
        self.assertFalse(has_blocking_conflicts([]))

    def test_error_severity_is_blocking(self):
        config = OmegaServConfig.from_dict({"options": {"trusted_proxy": {"enabled": True}}})
        self.assertTrue(has_blocking_conflicts(detect_conflicts(config)))


if __name__ == "__main__":
    unittest.main()
