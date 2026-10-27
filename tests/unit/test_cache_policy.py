import unittest

from omega_serv.domain.routing.cache_policy import (
    DEFAULT_CACHE_CONTROL,
    DEFAULT_EXTENSION_CACHE,
    CachePolicy,
    parse_cache_policy,
    resolve_cache_control,
)
from omega_serv.domain.routing.zone_resolver import Zone


class TestResolveCacheControl(unittest.TestCase):
    def test_default_used_when_no_zone_or_extension_match(self):
        policy = CachePolicy()
        self.assertEqual(resolve_cache_control("/x", "x.txt", policy), DEFAULT_CACHE_CONTROL)

    def test_extension_match(self):
        policy = CachePolicy(extensions={".css": "public, max-age=31536000, immutable"})
        self.assertEqual(resolve_cache_control("/style.css", "style.css", policy), "public, max-age=31536000, immutable")

    def test_zone_match_wins_over_extension(self):
        policy = CachePolicy(
            zones=(Zone("/admin/", "no-store"),),
            extensions={".css": "public, max-age=31536000"},
        )
        self.assertEqual(resolve_cache_control("/admin/style.css", "style.css", policy), "no-store")

    def test_parse_cache_policy_from_settings(self):
        settings = {
            "default": "public, max-age=3600",
            "zones": [{"path_prefix": "/admin/", "cache_control": "no-store"}],
            "extensions": {".js": "public, max-age=31536000"},
        }
        policy = parse_cache_policy(settings)
        self.assertEqual(policy.default, "public, max-age=3600")
        self.assertEqual(resolve_cache_control("/admin/x", "x", policy), "no-store")
        self.assertEqual(resolve_cache_control("/app.js", "app.js", policy), "public, max-age=31536000")


    def test_default_extension_rules_apply_until_the_config_has_its_own(self):
        """Decision utilisateur 2026-10-26 (etude performance, point 3) : Cache-Control par
        defaut pour images/medias/polices/CSS/JS, toujours modifiable."""
        policy = parse_cache_policy({})
        self.assertEqual(resolve_cache_control("/omega-serv/screenshots/1.png", "1.png", policy), "max-age=86400")
        self.assertEqual(resolve_cache_control("/assets/site.css", "site.css", policy), "max-age=3600")
        self.assertEqual(resolve_cache_control("/index.html", "index.html", policy), DEFAULT_CACHE_CONTROL)
        self.assertTrue(all("public" not in value for value in DEFAULT_EXTENSION_CACHE.values()))

    def test_an_explicit_table_replaces_the_defaults_even_empty(self):
        self.assertEqual(
            resolve_cache_control("/a.png", "a.png", parse_cache_policy({"extensions": {}})), DEFAULT_CACHE_CONTROL,
        )
        own = parse_cache_policy({"extensions": {".png": "no-store"}})
        self.assertEqual(resolve_cache_control("/a.png", "a.png", own), "no-store")
        self.assertEqual(resolve_cache_control("/a.css", "a.css", own), DEFAULT_CACHE_CONTROL)

if __name__ == "__main__":
    unittest.main()
