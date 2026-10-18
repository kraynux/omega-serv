"""Garde-fou "conflit avec la configuration du site" (OMEGA-SERV_PLAN-
DETAILLE_SENSITIVE_PATHS.md §3.10-2) : une liste qui bloque seule ne doit
jamais toucher une route reellement servie."""
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.config.validate_config import validate_config_environment
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.waf.keyword_list import find_route_conflicts
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestFindRouteConflicts(unittest.TestCase):
    def test_entry_matching_route_prefix(self):
        conflicts = find_route_conflicts(("/api",), "root", (("reverse_proxy", "/api/"),))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].source, "reverse_proxy")

    def test_entry_inside_route(self):
        self.assertEqual(len(find_route_conflicts(("/api/v1",), "root", (("aliases", "/api/"),))), 1)

    def test_unrelated_entry(self):
        self.assertEqual(find_route_conflicts(("/.env", "/apis"), "root", (("aliases", "/api/"),)), ())

    def test_any_segment_entry_matching_deep_route(self):
        self.assertEqual(len(find_route_conflicts(("/admin",), "any_segment", (("aliases", "/shop/admin/"),))), 1)

    def test_route_covered_by_exception_is_not_a_conflict(self):
        self.assertEqual(find_route_conflicts(("/api",), "root", (("reverse_proxy", "/api/"),), ("/api",)), ())

    def test_root_route_and_suffix_entries_ignored(self):
        self.assertEqual(find_route_conflicts(("/.env", "/*.bak"), "any_segment", (("reverse_proxy", "/"),)), ())


class TestConfigCheckRefusesConflictingBlockingList(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot" / "admin").mkdir(parents=True)
        keywords = self.root / "secure" / "waf" / "rules" / "keywords"
        keywords.mkdir(parents=True)
        (keywords / "l.txt").write_text("/.env\n/admin\n/api/v1\n/*.bak\n")
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _errors(self, **list_overrides):
        definition = {"id": "sensitive-paths-test", "scope": ["path"], "match": "path",
                      "file": "secure/waf/rules/keywords/l.txt", "weight": 6}
        definition.update(list_overrides)
        config = OmegaServConfig.from_dict({"options": {
            "waf": {"enabled": True, "rules": {"keyword_lists": [definition]}},
            "reverse_proxy": {"enabled": True, "zones": [
                {"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]},
            ]},
        }})
        return [e for e in validate_config_environment(config, self.filesystem, self.root) if "keyword_lists" in e]

    def test_blocking_list_conflicts_reported(self):
        errors = self._errors()
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("'/api/v1'" in e and "reverse_proxy" in e for e in errors))
        self.assertTrue(any("'/admin'" in e and "webroot" in e for e in errors))

    def test_observation_list_is_not_checked(self):
        self.assertEqual(self._errors(observe_only=True), [])

    def test_exceptions_resolve_the_conflicts(self):
        (self.root / "secure" / "waf" / "rules" / "keywords" / "l.txt").write_text(
            "/.env\n/admin\n/api/v1\n!/admin\n!/api/\n"
        )
        self.assertEqual(self._errors(), [])

    def test_non_blocking_weight_is_not_an_error(self):
        self.assertEqual(self._errors(weight=3), [])


if __name__ == "__main__":
    unittest.main()
