# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.routing.cache_policy import (
    DEFAULT_CACHE_CONTROL,
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


if __name__ == "__main__":
    unittest.main()
