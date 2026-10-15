import time
import unittest

from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    PROXY_LOAD_BALANCING_STRATEGIES,
    ProxyLoadBalancerState,
    ProxyZone,
    RoutingRule,
    UpstreamTarget,
    parse_proxy_zones,
    resolve_proxy_zone,
    resolve_routing_rule_upstream,
    resolve_sticky_upstream,
    sticky_cookie_value_for,
    upstream_key,
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

    def test_upstream_weight_defaults_to_one(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]}])
        self.assertEqual(zones[0].upstreams[0].weight, 1)

    def test_upstream_weight_parsed(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000, "weight": 5}]}])
        self.assertEqual(zones[0].upstreams[0].weight, 5)

    def test_upstream_max_concurrent_requests_defaults_to_none(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]}])
        self.assertIsNone(zones[0].upstreams[0].max_concurrent_requests)

    def test_upstream_max_concurrent_requests_parsed(self):
        zones = parse_proxy_zones([{
            "url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000, "max_concurrent_requests": 5}],
        }])
        self.assertEqual(zones[0].upstreams[0].max_concurrent_requests, 5)

    def test_upstream_active_health_check_defaults_to_disabled(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]}])
        self.assertFalse(zones[0].upstreams[0].active_health_check_enabled)
        self.assertEqual(zones[0].upstreams[0].active_health_check_path, "/")

    def test_upstream_active_health_check_parsed(self):
        zones = parse_proxy_zones([{
            "url_prefix": "/api/",
            "upstreams": [{
                "host": "127.0.0.1", "port": 3000,
                "active_health_check_enabled": True, "active_health_check_path": "/healthz",
            }],
        }])
        self.assertTrue(zones[0].upstreams[0].active_health_check_enabled)
        self.assertEqual(zones[0].upstreams[0].active_health_check_path, "/healthz")

    def test_load_balancing_defaults_to_round_robin(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/"}])
        self.assertEqual(zones[0].load_balancing, "round_robin")

    def test_load_balancing_parsed(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/", "load_balancing": "least_connections"}])
        self.assertEqual(zones[0].load_balancing, "least_connections")

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

    def test_max_concurrent_requests_none_is_valid(self):
        self.assertIsNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(host="127.0.0.1", port=3000, max_concurrent_requests=None),),
        )))

    def test_max_concurrent_requests_positive_is_valid(self):
        self.assertIsNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(host="127.0.0.1", port=3000, max_concurrent_requests=10),),
        )))

    def test_max_concurrent_requests_zero_is_invalid(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(host="127.0.0.1", port=3000, max_concurrent_requests=0),),
        )))

    def test_max_concurrent_requests_negative_is_invalid(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(host="127.0.0.1", port=3000, max_concurrent_requests=-1),),
        )))

    def test_active_health_check_path_invalid_when_disabled_is_ignored(self):
        self.assertIsNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(
                host="127.0.0.1", port=3000, active_health_check_enabled=False, active_health_check_path="pas-de-slash",
            ),),
        )))

    def test_active_health_check_path_must_start_with_slash_when_enabled(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(
                host="127.0.0.1", port=3000, active_health_check_enabled=True, active_health_check_path="pas-de-slash",
            ),),
        )))

    def test_active_health_check_path_valid_when_enabled(self):
        self.assertIsNone(validate_proxy_zone(self._zone(
            upstreams=(UpstreamTarget(
                host="127.0.0.1", port=3000, active_health_check_enabled=True, active_health_check_path="/healthz",
            ),),
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

    def test_invalid_upstream_weight(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(upstreams=(UpstreamTarget(host="127.0.0.1", port=3000, weight=0),))))

    def test_invalid_load_balancing(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(load_balancing="lottery")))

    def test_all_known_strategies_accepted(self):
        for strategy in PROXY_LOAD_BALANCING_STRATEGIES:
            self.assertIsNone(validate_proxy_zone(self._zone(load_balancing=strategy)), strategy)


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


class TestProxyLoadBalancerState(unittest.TestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def _zone(self, **overrides):
        defaults = {"url_prefix": "/api/", "upstreams": (self._UPSTREAM_A, self._UPSTREAM_B)}
        defaults.update(overrides)
        return ProxyZone(**defaults)

    def test_single_upstream_always_selected(self):
        zone = self._zone(upstreams=(self._UPSTREAM_A,))
        state = ProxyLoadBalancerState()
        self.assertEqual(state.select(zone, "203.0.113.1"), self._UPSTREAM_A)
        self.assertEqual(state.select(zone, "203.0.113.1"), self._UPSTREAM_A)

    def test_round_robin_alternates(self):
        zone = self._zone(load_balancing="round_robin")
        state = ProxyLoadBalancerState()
        picks = [state.select(zone, "203.0.113.1") for _ in range(4)]
        self.assertEqual(picks, [self._UPSTREAM_A, self._UPSTREAM_B, self._UPSTREAM_A, self._UPSTREAM_B])

    def test_round_robin_independent_counters_per_zone(self):
        zone_a = self._zone(url_prefix="/a/")
        zone_b = self._zone(url_prefix="/b/")
        state = ProxyLoadBalancerState()
        self.assertEqual(state.select(zone_a, "203.0.113.1"), self._UPSTREAM_A)
        self.assertEqual(state.select(zone_b, "203.0.113.1"), self._UPSTREAM_A)
        self.assertEqual(state.select(zone_a, "203.0.113.1"), self._UPSTREAM_B)
        self.assertEqual(state.select(zone_b, "203.0.113.1"), self._UPSTREAM_B)

    def test_round_robin_state_survives_upstream_reordering(self):
        """§27.1 : l'etat est cle par host:port, jamais par position -
        reordonner le tuple `upstreams` d'une zone (ex. via le TUI) ne
        doit pas faire "sauter" ou repeter une selection."""
        zone = self._zone(upstreams=(self._UPSTREAM_A, self._UPSTREAM_B))
        state = ProxyLoadBalancerState()
        state.select(zone, "203.0.113.1")
        reordered_zone = self._zone(upstreams=(self._UPSTREAM_B, self._UPSTREAM_A))
        picks = [state.select(reordered_zone, "203.0.113.1") for _ in range(2)]
        self.assertEqual(set(picks), {self._UPSTREAM_A, self._UPSTREAM_B})

    def test_weighted_round_robin_respects_weight_ratio(self):
        heavy = UpstreamTarget(host="10.0.0.3", port=3000, weight=3)
        light = UpstreamTarget(host="10.0.0.4", port=3000, weight=1)
        zone = self._zone(upstreams=(heavy, light), load_balancing="weighted_round_robin")
        state = ProxyLoadBalancerState()
        picks = [state.select(zone, "203.0.113.1") for _ in range(4)]
        self.assertEqual(picks.count(heavy), 3)
        self.assertEqual(picks.count(light), 1)

    def test_least_connections_prefers_idle_upstream(self):
        zone = self._zone(load_balancing="least_connections")
        state = ProxyLoadBalancerState()
        state.acquire(zone.url_prefix, self._UPSTREAM_A)
        state.acquire(zone.url_prefix, self._UPSTREAM_A)
        self.assertEqual(state.select(zone, "203.0.113.1"), self._UPSTREAM_B)

    def test_least_connections_release_frees_capacity(self):
        zone = self._zone(load_balancing="least_connections")
        state = ProxyLoadBalancerState()
        state.acquire(zone.url_prefix, self._UPSTREAM_A)
        state.acquire(zone.url_prefix, self._UPSTREAM_A)
        state.release(zone.url_prefix, self._UPSTREAM_A)
        state.release(zone.url_prefix, self._UPSTREAM_A)
        self.assertEqual(state.select(zone, "203.0.113.1"), self._UPSTREAM_A)

    def test_weighted_least_connections_uses_ratio_not_raw_count(self):
        heavy = UpstreamTarget(host="10.0.0.3", port=3000, weight=2)
        light = UpstreamTarget(host="10.0.0.4", port=3000, weight=1)
        zone = self._zone(upstreams=(heavy, light), load_balancing="weighted_least_connections")
        state = ProxyLoadBalancerState()
        state.acquire(zone.url_prefix, heavy)
        state.acquire(zone.url_prefix, heavy)
        # heavy : 2 connexions / poids 2 = 1.0 ; light : 0 connexions / poids 1 = 0.0 -> light gagne
        self.assertEqual(state.select(zone, "203.0.113.1"), light)
        state.acquire(zone.url_prefix, light)
        # heavy : 2/2 = 1.0 ; light : 1/1 = 1.0 -> egalite, min() retient le premier (heavy)
        self.assertEqual(state.select(zone, "203.0.113.1"), heavy)

    def test_ip_hash_is_deterministic_for_same_client(self):
        zone = self._zone(load_balancing="ip_hash")
        state = ProxyLoadBalancerState()
        first = state.select(zone, "198.51.100.7")
        for _ in range(5):
            self.assertEqual(state.select(zone, "198.51.100.7"), first)

    def test_ip_hash_can_differ_for_different_clients(self):
        zone = self._zone(load_balancing="ip_hash")
        state = ProxyLoadBalancerState()
        picked = {state.select(zone, f"198.51.100.{i}") for i in range(20)}
        self.assertEqual(picked, {self._UPSTREAM_A, self._UPSTREAM_B})

    def test_least_response_time_prefers_untested_upstream(self):
        zone = self._zone(load_balancing="least_response_time")
        state = ProxyLoadBalancerState()
        state.record_response_time(zone.url_prefix, self._UPSTREAM_A, 0.5)
        self.assertEqual(state.select(zone, "203.0.113.1"), self._UPSTREAM_B)

    def test_least_response_time_prefers_faster_recorded_average(self):
        zone = self._zone(load_balancing="least_response_time")
        state = ProxyLoadBalancerState()
        state.record_response_time(zone.url_prefix, self._UPSTREAM_A, 0.1)
        state.record_response_time(zone.url_prefix, self._UPSTREAM_B, 0.9)
        self.assertEqual(state.select(zone, "203.0.113.1"), self._UPSTREAM_A)

    def test_record_response_time_is_an_exponential_moving_average(self):
        state = ProxyLoadBalancerState()
        state.record_response_time("/api/", self._UPSTREAM_A, 1.0)
        state.record_response_time("/api/", self._UPSTREAM_A, 0.0)
        self.assertAlmostEqual(state._response_time_avg_seconds["/api/"][upstream_key(self._UPSTREAM_A)], 0.7)

    def test_acquire_and_release_are_keyed_by_stable_upstream_identity(self):
        """§27.1 : reordonner le tuple d'upstreams ne doit jamais
        confondre les compteurs de connexions actives."""
        state = ProxyLoadBalancerState()
        state.acquire("/api/", self._UPSTREAM_A)
        state.acquire("/api/", self._UPSTREAM_A)
        reordered = ProxyZone(url_prefix="/api/", upstreams=(self._UPSTREAM_B, self._UPSTREAM_A), load_balancing="least_connections")
        self.assertEqual(state.select(reordered, "203.0.113.1"), self._UPSTREAM_B)

    def test_release_never_goes_negative(self):
        state = ProxyLoadBalancerState()
        state.release("/api/", self._UPSTREAM_A)
        zone = self._zone(load_balancing="least_connections")
        self.assertIn(state.select(zone, "203.0.113.1"), (self._UPSTREAM_A, self._UPSTREAM_B))


class TestStickySessionParsingAndValidation(unittest.TestCase):
    def test_sticky_fields_default(self):
        zones = parse_proxy_zones([{"url_prefix": "/api/"}])
        self.assertFalse(zones[0].sticky_session_enabled)
        self.assertEqual(zones[0].sticky_cookie_name, "omega_proxy_sticky")
        self.assertEqual(zones[0].sticky_cookie_max_age_seconds, 7200)

    def test_sticky_fields_parsed(self):
        zones = parse_proxy_zones([{
            "url_prefix": "/api/", "sticky_session_enabled": True,
            "sticky_cookie_name": "mon_cookie", "sticky_cookie_max_age_seconds": 60,
        }])
        self.assertTrue(zones[0].sticky_session_enabled)
        self.assertEqual(zones[0].sticky_cookie_name, "mon_cookie")
        self.assertEqual(zones[0].sticky_cookie_max_age_seconds, 60)

    def test_routing_rules_parsed(self):
        zones = parse_proxy_zones([{
            "url_prefix": "/api/",
            "routing_rules": [{"header_name": "X-Canary", "pattern": "true", "upstream_key": "10.0.0.1:3000"}],
        }])
        self.assertEqual(
            zones[0].routing_rules,
            (RoutingRule(header_name="X-Canary", pattern="true", upstream_key="10.0.0.1:3000"),),
        )

    def _zone(self, **overrides):
        defaults = {"url_prefix": "/api/", "upstreams": (UpstreamTarget(host="127.0.0.1", port=3000),)}
        defaults.update(overrides)
        return ProxyZone(**defaults)

    def test_sticky_enabled_with_empty_cookie_name_is_invalid(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(sticky_session_enabled=True, sticky_cookie_name="  ")))

    def test_sticky_enabled_with_non_positive_max_age_is_invalid(self):
        self.assertIsNotNone(validate_proxy_zone(self._zone(sticky_session_enabled=True, sticky_cookie_max_age_seconds=0)))

    def test_sticky_disabled_ignores_invalid_cookie_name(self):
        self.assertIsNone(validate_proxy_zone(self._zone(sticky_session_enabled=False, sticky_cookie_name="")))

    def test_routing_rule_empty_header_name_is_invalid(self):
        rule = RoutingRule(header_name="", pattern="true", upstream_key="127.0.0.1:3000")
        self.assertIsNotNone(validate_proxy_zone(self._zone(routing_rules=(rule,))))

    def test_routing_rule_empty_pattern_is_invalid(self):
        rule = RoutingRule(header_name="X-Canary", pattern="", upstream_key="127.0.0.1:3000")
        self.assertIsNotNone(validate_proxy_zone(self._zone(routing_rules=(rule,))))

    def test_routing_rule_unknown_upstream_key_is_invalid(self):
        rule = RoutingRule(header_name="X-Canary", pattern="true", upstream_key="10.0.0.99:9999")
        self.assertIsNotNone(validate_proxy_zone(self._zone(routing_rules=(rule,))))

    def test_routing_rule_known_upstream_key_is_valid(self):
        rule = RoutingRule(header_name="X-Canary", pattern="true", upstream_key="127.0.0.1:3000")
        self.assertIsNone(validate_proxy_zone(self._zone(routing_rules=(rule,))))


class TestStickyCookieValueFor(unittest.TestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def test_deterministic_for_same_upstream(self):
        self.assertEqual(sticky_cookie_value_for(self._UPSTREAM_A), sticky_cookie_value_for(self._UPSTREAM_A))

    def test_different_for_different_upstreams(self):
        self.assertNotEqual(sticky_cookie_value_for(self._UPSTREAM_A), sticky_cookie_value_for(self._UPSTREAM_B))

    def test_never_exposes_host_port_in_clear(self):
        value = sticky_cookie_value_for(self._UPSTREAM_A)
        self.assertNotIn("10.0.0.1", value)
        self.assertNotIn("3000", value)


class TestResolveStickyUpstream(unittest.TestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def _zone(self):
        return ProxyZone(url_prefix="/api/", upstreams=(self._UPSTREAM_A, self._UPSTREAM_B), sticky_session_enabled=True)

    def test_matching_cookie_value_resolves_to_its_upstream(self):
        zone = self._zone()
        cookie_value = sticky_cookie_value_for(self._UPSTREAM_B)
        self.assertEqual(resolve_sticky_upstream(zone, cookie_value), self._UPSTREAM_B)

    def test_unknown_cookie_value_resolves_to_none(self):
        self.assertIsNone(resolve_sticky_upstream(self._zone(), "forged-value-not-matching-anything"))

    def test_cookie_value_of_removed_upstream_resolves_to_none(self):
        """Un upstream retire de la zone depuis la pose du cookie ne
        doit jamais etre retrouve - la fonction ne connait que les
        upstreams ACTUELS de `zone.upstreams`."""
        removed = UpstreamTarget(host="10.0.0.99", port=9999)
        cookie_value = sticky_cookie_value_for(removed)
        self.assertIsNone(resolve_sticky_upstream(self._zone(), cookie_value))


class TestResolveRoutingRuleUpstream(unittest.TestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def _zone(self, *rules):
        return ProxyZone(url_prefix="/api/", upstreams=(self._UPSTREAM_A, self._UPSTREAM_B), routing_rules=rules)

    def test_exact_match_routes_to_named_upstream(self):
        rule = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule)
        self.assertEqual(resolve_routing_rule_upstream(zone, {"x-canary": "true"}.get), self._UPSTREAM_B)

    def test_no_matching_header_value_falls_through(self):
        rule = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule)
        self.assertIsNone(resolve_routing_rule_upstream(zone, {"x-canary": "false"}.get))

    def test_missing_header_falls_through(self):
        rule = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule)
        self.assertIsNone(resolve_routing_rule_upstream(zone, {}.get))

    def test_trailing_star_pattern_matches_as_prefix(self):
        rule = RoutingRule(header_name="user-agent", pattern="CanaryBot/*", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule)
        self.assertEqual(
            resolve_routing_rule_upstream(zone, {"user-agent": "CanaryBot/1.2"}.get), self._UPSTREAM_B,
        )

    def test_first_matching_rule_wins(self):
        rule_a = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_A))
        rule_b = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule_a, rule_b)
        self.assertEqual(resolve_routing_rule_upstream(zone, {"x-canary": "true"}.get), self._UPSTREAM_A)


class TestRealLoadStrategy(unittest.TestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def _zone(self, **overrides):
        defaults = {
            "url_prefix": "/api/", "upstreams": (self._UPSTREAM_A, self._UPSTREAM_B), "load_balancing": "real_load",
        }
        defaults.update(overrides)
        return ProxyZone(**defaults)

    def test_picks_the_lowest_scored_upstream(self):
        zone = self._zone()
        health_state = ProxyHealthState()
        now = time.monotonic()
        health_state.record_load_sample(zone.url_prefix, self._UPSTREAM_A, 80.0, smoothing_samples=3, now=now)
        health_state.record_load_sample(zone.url_prefix, self._UPSTREAM_B, 20.0, smoothing_samples=3, now=now)
        state = ProxyLoadBalancerState()
        self.assertEqual(
            state.select(zone, "203.0.113.1", health_state=health_state), self._UPSTREAM_B,
        )

    def test_falls_back_to_least_connections_when_no_scores_available(self):
        zone = self._zone()
        health_state = ProxyHealthState()
        state = ProxyLoadBalancerState()
        state.acquire(zone.url_prefix, self._UPSTREAM_A)
        self.assertEqual(
            state.select(zone, "203.0.113.1", health_state=health_state), self._UPSTREAM_B,
        )

    def test_unscored_upstream_is_simply_excluded_not_a_failure(self):
        """Un upstream sans score (ex: declaratif en panne) ne doit pas
        faire echouer la strategie - seulement etre ignore si un AUTRE
        upstream a un score exploitable."""
        zone = self._zone()
        health_state = ProxyHealthState()
        health_state.record_load_sample(
            zone.url_prefix, self._UPSTREAM_B, 50.0, smoothing_samples=3, now=time.monotonic(),
        )
        state = ProxyLoadBalancerState()
        self.assertEqual(
            state.select(zone, "203.0.113.1", health_state=health_state), self._UPSTREAM_B,
        )

    def test_without_health_state_falls_back_to_round_robin(self):
        zone = self._zone()
        state = ProxyLoadBalancerState()
        picked = state.select(zone, "203.0.113.1")
        self.assertIn(picked, (self._UPSTREAM_A, self._UPSTREAM_B))


class TestIsAtCapacity(unittest.TestCase):
    def test_unlimited_by_default(self):
        state = ProxyLoadBalancerState()
        upstream = UpstreamTarget(host="10.0.0.1", port=3000)
        for _ in range(1000):
            state.acquire("/api/", upstream)
        self.assertFalse(state.is_at_capacity("/api/", upstream))

    def test_below_limit_is_not_at_capacity(self):
        state = ProxyLoadBalancerState()
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, max_concurrent_requests=3)
        state.acquire("/api/", upstream)
        state.acquire("/api/", upstream)
        self.assertFalse(state.is_at_capacity("/api/", upstream))

    def test_at_limit_is_at_capacity(self):
        state = ProxyLoadBalancerState()
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, max_concurrent_requests=2)
        state.acquire("/api/", upstream)
        state.acquire("/api/", upstream)
        self.assertTrue(state.is_at_capacity("/api/", upstream))

    def test_release_frees_capacity(self):
        state = ProxyLoadBalancerState()
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, max_concurrent_requests=1)
        state.acquire("/api/", upstream)
        self.assertTrue(state.is_at_capacity("/api/", upstream))
        state.release("/api/", upstream)
        self.assertFalse(state.is_at_capacity("/api/", upstream))

    def test_capacity_is_independent_per_zone(self):
        state = ProxyLoadBalancerState()
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, max_concurrent_requests=1)
        state.acquire("/api/", upstream)
        self.assertTrue(state.is_at_capacity("/api/", upstream))
        self.assertFalse(state.is_at_capacity("/autre/", upstream))


if __name__ == "__main__":
    unittest.main()
