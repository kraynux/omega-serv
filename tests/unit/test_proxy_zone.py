# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.routing.proxy_zone import (
    ProxyRoundRobinState,
    ProxyZone,
    UpstreamTarget,
    parse_proxy_zones,
    resolve_proxy_zone,
    validate_proxy_zone,
)


class TestParseProxyZones(unittest.TestCase):
    def test_parses_all_fields(self):
        zones = parse_proxy_zones([{
            "url_prefix": "/api/",
            "upstreams": [
                {"host": "127.0.0.1", "port": 3000},
                {"host": "127.0.0.1", "port": 3001, "use_tls": True},
            ],
            "connect_timeout_seconds": 2.5,
            "read_timeout_seconds": 10.0,
            "preserve_host_header": True,
            "verify_upstream_tls": False,
            "websocket_enabled": True,
        }])
        self.assertEqual(len(zones), 1)
        zone = zones[0]
        self.assertEqual(zone.url_prefix, "/api/")
        self.assertEqual(
            zone.upstreams,
            (
                UpstreamTarget(host="127.0.0.1", port=3000),
                UpstreamTarget(host="127.0.0.1", port=3001, use_tls=True),
            ),
        )
        self.assertEqual(zone.connect_timeout_seconds, 2.5)
        self.assertEqual(zone.read_timeout_seconds, 10.0)
        self.assertTrue(zone.preserve_host_header)
        self.assertFalse(zone.verify_upstream_tls)
        self.assertTrue(zone.websocket_enabled)

    def test_defaults_applied(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/"}])
        zone = zones[0]
        self.assertEqual(zone.upstreams, ())
        self.assertEqual(zone.connect_timeout_seconds, 5.0)
        self.assertEqual(zone.read_timeout_seconds, 30.0)
        self.assertFalse(zone.preserve_host_header)
        self.assertTrue(zone.verify_upstream_tls)
        self.assertFalse(zone.websocket_enabled)

    def test_upstream_use_tls_defaults_to_false(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]}])
        self.assertFalse(zones[0].upstreams[0].use_tls)

    def test_empty_list(self):
        self.assertEqual(parse_proxy_zones([]), [])


class TestValidateProxyZone(unittest.TestCase):
    def _zone(self, **overrides):
        defaults = {"url_prefix": "/api/", "upstreams": (UpstreamTarget(host="127.0.0.1", port=3000),)}
        defaults.update(overrides)
        return ProxyZone(**defaults)

    def test_valid_zone_returns_none(self):
        self.assertIsNone(validate_proxy_zone(self._zone()))

    def test_valid_zone_multiple_upstreams_returns_none(self):
        self.assertIsNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(host="127.0.0.1", port=3000), UpstreamTarget(host="127.0.0.1", port=3001)),
        )))

    def test_prefix_without_leading_slash(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(url_prefix="api/")))

    def test_no_upstreams(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(upstreams=())))

    def test_missing_upstream_host(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(upstreams=(UpstreamTarget(host="", port=3000),))))

    def test_invalid_port_zero(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(upstreams=(UpstreamTarget(host="127.0.0.1", port=0),))))

    def test_invalid_port_too_large(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(upstreams=(UpstreamTarget(host="127.0.0.1", port=70000),))))

    def test_one_bad_upstream_among_valid_ones_fails(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(upstreams=(
            UpstreamTarget(host="127.0.0.1", port=3000), UpstreamTarget(host="127.0.0.1", port=0),
        ))))

    def test_non_positive_connect_timeout(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(connect_timeout_seconds=0)))

    def test_non_positive_read_timeout(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(read_timeout_seconds=-1)))


class TestResolveProxyZone(unittest.TestCase):
    def test_no_zones_returns_none(self):
        self.assertIsNone(resolve_proxy_zone("/api/foo", []))

    def test_no_match_returns_none(self):
        zones = [ProxyZone(url_prefix="/app/", upstreams=(UpstreamTarget(host="127.0.0.1", port=3000),))]
        self.assertIsNone(resolve_proxy_zone("/other/", zones))

    def test_longest_prefix_wins(self):
        general = ProxyZone(url_prefix="/api/", upstreams=(UpstreamTarget(host="127.0.0.1", port=3000),))
        specific = ProxyZone(url_prefix="/api/v2/", upstreams=(UpstreamTarget(host="127.0.0.1", port=4000),))
        zones = [general, specific]
        matched = resolve_proxy_zone("/api/v2/users", zones)
        self.assertIs(matched, specific)


class TestProxyRoundRobinState(unittest.TestCase):
    def test_single_upstream_always_picks_index_zero(self):
        state = ProxyRoundRobinState()
        self.assertEqual(state.pick("/api/", 1), 0)
        self.assertEqual(state.pick("/api/", 1), 0)

    def test_rotates_across_successive_picks(self):
        state = ProxyRoundRobinState()
        picks = [state.pick("/api/", 3) for _ in range(7)]
        self.assertEqual(picks, [0, 1, 2, 0, 1, 2, 0])

    def test_independent_counters_per_zone(self):
        state = ProxyRoundRobinState()
        self.assertEqual(state.pick("/api/", 2), 0)
        self.assertEqual(state.pick("/app/", 2), 0)
        self.assertEqual(state.pick("/api/", 2), 1)
        self.assertEqual(state.pick("/app/", 2), 1)


if __name__ == "__main__":
    unittest.main()
