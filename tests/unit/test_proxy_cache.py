import unittest

from omega_serv.domain.routing.proxy_cache import (
    ProxyCacheEntry,
    entry_matches_request,
    is_cacheable_request,
    is_cacheable_response,
    is_expired,
    parse_cache_control_header,
    parse_vary_header,
    primary_cache_key,
    resolve_cache_ttl_seconds,
    variant_cache_key,
)


class TestParseCacheControlHeader(unittest.TestCase):
    def test_none_is_all_false(self):
        directives = parse_cache_control_header(None)
        self.assertFalse(directives.no_store)
        self.assertFalse(directives.no_cache)
        self.assertFalse(directives.private)
        self.assertIsNone(directives.max_age)

    def test_no_store(self):
        self.assertTrue(parse_cache_control_header("no-store").no_store)

    def test_no_cache(self):
        self.assertTrue(parse_cache_control_header("no-cache").no_cache)

    def test_private(self):
        self.assertTrue(parse_cache_control_header("private").private)

    def test_max_age_parsed(self):
        self.assertEqual(parse_cache_control_header("max-age=120").max_age, 120)

    def test_multiple_directives_combined(self):
        directives = parse_cache_control_header("public, max-age=30")
        self.assertEqual(directives.max_age, 30)
        self.assertFalse(directives.no_store)

    def test_malformed_max_age_is_ignored(self):
        self.assertIsNone(parse_cache_control_header("max-age=not-a-number").max_age)


class TestParseVaryHeader(unittest.TestCase):
    def test_none_is_empty(self):
        self.assertEqual(parse_vary_header(None), ())

    def test_single_header(self):
        self.assertEqual(parse_vary_header("Accept-Encoding"), ("Accept-Encoding",))

    def test_multiple_headers(self):
        self.assertEqual(parse_vary_header("Accept-Encoding, Accept-Language"), ("Accept-Encoding", "Accept-Language"))


class TestResolveCacheTtlSeconds(unittest.TestCase):
    def test_no_cache_control_falls_back_to_default(self):
        ttl = resolve_cache_ttl_seconds((), respect_upstream_headers=True, default_ttl_seconds=60.0)
        self.assertEqual(ttl, 60.0)

    def test_max_age_overrides_default(self):
        ttl = resolve_cache_ttl_seconds(
            (("Cache-Control", "max-age=30"),), respect_upstream_headers=True, default_ttl_seconds=60.0,
        )
        self.assertEqual(ttl, 30.0)

    def test_no_store_means_never_cache(self):
        ttl = resolve_cache_ttl_seconds(
            (("Cache-Control", "no-store"),), respect_upstream_headers=True, default_ttl_seconds=60.0,
        )
        self.assertIsNone(ttl)

    def test_private_means_never_cache(self):
        ttl = resolve_cache_ttl_seconds(
            (("Cache-Control", "private"),), respect_upstream_headers=True, default_ttl_seconds=60.0,
        )
        self.assertIsNone(ttl)

    def test_ignoring_upstream_headers_always_uses_default_even_with_no_store(self):
        """§21 : `cache_respect_upstream_headers=False` est un raccourci
        EXPLICITEMENT DANGEREUX - ignore meme `no-store`."""
        ttl = resolve_cache_ttl_seconds(
            (("Cache-Control", "no-store"),), respect_upstream_headers=False, default_ttl_seconds=60.0,
        )
        self.assertEqual(ttl, 60.0)


class TestIsCacheableRequestAndResponse(unittest.TestCase):
    def test_get_is_cacheable(self):
        self.assertTrue(is_cacheable_request("GET"))

    def test_head_is_cacheable(self):
        self.assertTrue(is_cacheable_request("HEAD"))

    def test_post_is_never_cacheable(self):
        self.assertFalse(is_cacheable_request("POST"))

    def test_error_status_is_never_cacheable(self):
        self.assertFalse(is_cacheable_response(500, (), allow_set_cookie=True))

    def test_404_is_never_cacheable(self):
        self.assertFalse(is_cacheable_response(404, (), allow_set_cookie=True))

    def test_200_is_cacheable(self):
        self.assertTrue(is_cacheable_response(200, (), allow_set_cookie=False))

    def test_set_cookie_blocks_caching_by_default(self):
        self.assertFalse(is_cacheable_response(200, (("Set-Cookie", "a=b"),), allow_set_cookie=False))

    def test_set_cookie_allowed_when_zone_assumes_it(self):
        self.assertTrue(is_cacheable_response(200, (("Set-Cookie", "a=b"),), allow_set_cookie=True))


class TestPrimaryCacheKey(unittest.TestCase):
    def test_deterministic(self):
        key_a = primary_cache_key("GET", "example.com", "/api/users", "page=2")
        key_b = primary_cache_key("GET", "example.com", "/api/users", "page=2")
        self.assertEqual(key_a, key_b)

    def test_differs_by_method(self):
        self.assertNotEqual(
            primary_cache_key("GET", "example.com", "/api/users", ""),
            primary_cache_key("HEAD", "example.com", "/api/users", ""),
        )

    def test_differs_by_query(self):
        self.assertNotEqual(
            primary_cache_key("GET", "example.com", "/api/users", "page=1"),
            primary_cache_key("GET", "example.com", "/api/users", "page=2"),
        )


class TestVariantCacheKey(unittest.TestCase):
    def test_deterministic(self):
        primary = primary_cache_key("GET", "example.com", "/api/users", "")
        key_a = variant_cache_key(primary, ("Accept-Encoding",), ("gzip",))
        key_b = variant_cache_key(primary, ("Accept-Encoding",), ("gzip",))
        self.assertEqual(key_a, key_b)

    def test_differs_by_vary_value(self):
        primary = primary_cache_key("GET", "example.com", "/api/users", "")
        self.assertNotEqual(
            variant_cache_key(primary, ("Accept-Encoding",), ("gzip",)),
            variant_cache_key(primary, ("Accept-Encoding",), ("br",)),
        )

    def test_always_prefixed_by_the_primary_key(self):
        primary = primary_cache_key("GET", "example.com", "/api/users", "")
        self.assertTrue(variant_cache_key(primary, (), ()).startswith(f"{primary}--"))

    def test_no_vary_still_produces_a_stable_key(self):
        primary = primary_cache_key("GET", "example.com", "/api/users", "")
        self.assertEqual(variant_cache_key(primary, (), ()), variant_cache_key(primary, (), ()))

    def test_differs_by_primary_key_even_with_identical_vary(self):
        primary_a = primary_cache_key("GET", "example.com", "/api/users", "")
        primary_b = primary_cache_key("GET", "example.com", "/api/orders", "")
        self.assertNotEqual(
            variant_cache_key(primary_a, ("Accept-Encoding",), ("gzip",)),
            variant_cache_key(primary_b, ("Accept-Encoding",), ("gzip",)),
        )


class TestEntryMatchesRequest(unittest.TestCase):
    def _entry(self, **overrides):
        defaults = {
            "status_code": 200, "headers": (), "body": b"", "stored_at": 0.0, "ttl_seconds": 60.0,
            "vary_header_names": (), "vary_header_values": (),
        }
        defaults.update(overrides)
        return ProxyCacheEntry(**defaults)

    def test_no_vary_always_matches(self):
        entry = self._entry()
        self.assertTrue(entry_matches_request(entry, {}.get))

    def test_matching_vary_value(self):
        entry = self._entry(vary_header_names=("accept-encoding",), vary_header_values=("gzip",))
        self.assertTrue(entry_matches_request(entry, {"accept-encoding": "gzip"}.get))

    def test_mismatching_vary_value(self):
        entry = self._entry(vary_header_names=("accept-encoding",), vary_header_values=("gzip",))
        self.assertFalse(entry_matches_request(entry, {"accept-encoding": "br"}.get))

    def test_missing_header_treated_as_empty_string(self):
        entry = self._entry(vary_header_names=("accept-encoding",), vary_header_values=("",))
        self.assertTrue(entry_matches_request(entry, {}.get))


class TestIsExpired(unittest.TestCase):
    def test_fresh_entry_is_not_expired(self):
        entry = ProxyCacheEntry(
            status_code=200, headers=(), body=b"", stored_at=100.0, ttl_seconds=60.0,
            vary_header_names=(), vary_header_values=(),
        )
        self.assertFalse(is_expired(entry, now=110.0))

    def test_expired_entry(self):
        entry = ProxyCacheEntry(
            status_code=200, headers=(), body=b"", stored_at=100.0, ttl_seconds=60.0,
            vary_header_names=(), vary_header_values=(),
        )
        self.assertTrue(is_expired(entry, now=200.0))


if __name__ == "__main__":
    unittest.main()
