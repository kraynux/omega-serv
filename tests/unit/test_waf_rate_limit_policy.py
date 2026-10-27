"""Regles de debit par dossier / IP-reseau (OMEGA-SERV_ETUDE_RATE_LIMIT_
EXCLUSIONS.md, decisions D1-D5)."""
import re
import unittest
from datetime import datetime, timezone

from omega_serv.application.security.evaluate_waf_request import evaluate_waf_request
from omega_serv.domain.logging.waf_alert_format import WafAlertEntry, format_waf_alert_line
from omega_serv.domain.security.waf.config import (
    RateLimitConfig,
    WafLoggingConfig,
    parse_waf_config,
    validate_waf_config,
)
from omega_serv.domain.security.waf.exclusions import matches_any_prefix
from omega_serv.domain.security.waf.rate_limit_policy import (
    effective_source_policies,
    is_trusted_rate_limit_source,
    select_rate_limit,
)
from omega_serv.domain.security.waf.reputation import DEFAULT_NEVER_AUTO_BLOCK
from omega_serv.ports.rate_limit_port import RateLimitCheckResult
from tests.unit.test_evaluate_waf_request import (
    _ALLOW,
    _FakeBlocklist,
    _FakeReputationTracker,
    _FakeWafPort,
    _request,
)


def _rate_limit(**data) -> RateLimitConfig:
    return RateLimitConfig.from_dict(data)


class _CountingRateLimit:
    """Token bucket simplifie : refuse a partir de la (requests+1)-ieme
    requete d'une meme cle ; enregistre les cles vues."""

    def __init__(self):
        self.counts: dict[str, int] = {}

    def check(self, key, requests, window_seconds):
        self.counts[key] = self.counts.get(key, 0) + 1
        allowed = self.counts[key] <= requests
        return RateLimitCheckResult(allowed=allowed, retry_after_seconds=None if allowed else 5)

    def reset(self, key=None):
        self.counts.clear()


class TestPrefixSegmentBoundary(unittest.TestCase):
    def test_neighbour_path_no_longer_matches(self):
        self.assertTrue(matches_any_prefix("/images/a.png", ("/images",)))
        self.assertTrue(matches_any_prefix("/images", ("/images",)))
        self.assertFalse(matches_any_prefix("/images-malveillant", ("/images",)))

    def test_trailing_slash_is_cosmetic(self):
        self.assertTrue(matches_any_prefix("/images", ("/images/",)))
        self.assertTrue(matches_any_prefix("/images/x", ("/images/",)))

    def test_root_matches_everything(self):
        self.assertTrue(matches_any_prefix("/anything", ("/",)))

    def test_healthz_default_unchanged(self):
        self.assertTrue(matches_any_prefix("/healthz", ("/healthz",)))


class TestSelectRateLimit(unittest.TestCase):
    def test_global_when_no_rule(self):
        selected = select_rate_limit("/", "203.0.113.1", _rate_limit())
        self.assertEqual((selected.key, selected.requests), ("203.0.113.1", 60))

    def test_path_rule_replaces_global_with_own_counter(self):
        config = _rate_limit(path_policies=[{"prefix": "/shots/", "requests": 600, "window_seconds": 60}])
        selected = select_rate_limit("/shots/a.png", "203.0.113.1", config)
        self.assertEqual(selected.requests, 600)
        self.assertNotEqual(selected.key, "203.0.113.1")

    def test_path_rule_can_be_lower_than_global(self):
        config = _rate_limit(path_policies=[{"prefix": "/login", "requests": 5}])
        self.assertEqual(select_rate_limit("/login", "203.0.113.1", config).requests, 5)

    def test_longest_path_prefix_wins(self):
        config = _rate_limit(path_policies=[
            {"prefix": "/a", "requests": 10}, {"prefix": "/a/b", "requests": 20},
        ])
        self.assertEqual(select_rate_limit("/a/b/c", "203.0.113.1", config).requests, 20)

    def test_neighbour_path_falls_back_to_global(self):
        config = _rate_limit(path_policies=[{"prefix": "/images", "requests": 600}])
        self.assertEqual(select_rate_limit("/images-x", "203.0.113.1", config).requests, 60)

    def test_source_rule_applies_outside_path_rules(self):
        config = _rate_limit(source_policies=[{"network": "100.64.0.0/10", "requests": 0}])
        self.assertEqual(select_rate_limit("/", "100.100.1.2", config).requests, 0)

    def test_path_rule_wins_over_source_rule(self):
        config = _rate_limit(
            path_policies=[{"prefix": "/shots", "requests": 600}],
            source_policies=[{"network": "100.64.0.0/10", "requests": 0}],
        )
        self.assertEqual(select_rate_limit("/shots/x", "100.100.1.2", config).requests, 600)

    def test_most_specific_network_wins(self):
        config = _rate_limit(source_policies=[
            {"network": "10.0.0.0/8", "requests": 100}, {"network": "10.1.2.3/32", "requests": 7},
        ])
        self.assertEqual(select_rate_limit("/", "10.1.2.3", config).requests, 7)
        self.assertEqual(select_rate_limit("/", "10.9.9.9", config).requests, 100)

    def test_ipv4_mapped_ipv6_is_normalized(self):
        config = _rate_limit(source_policies=[{"network": "10.0.0.0/8", "requests": 3}])
        self.assertEqual(select_rate_limit("/", "::ffff:10.0.0.1", config).requests, 3)


class TestTrustedSource(unittest.TestCase):
    def test_never_auto_block_is_trusted(self):
        self.assertTrue(is_trusted_rate_limit_source("100.100.1.2", DEFAULT_NEVER_AUTO_BLOCK, ()))

    def test_public_ip_not_trusted(self):
        self.assertFalse(is_trusted_rate_limit_source("203.0.113.1", DEFAULT_NEVER_AUTO_BLOCK, ()))

    def test_rule_marked_trusted(self):
        policies = _rate_limit(source_policies=[{"network": "198.51.100.0/24", "requests": 0, "trusted": True}]).source_policies
        self.assertTrue(is_trusted_rate_limit_source("198.51.100.9", (), policies))

    def test_rule_not_marked_trusted(self):
        policies = _rate_limit(source_policies=[{"network": "198.51.100.0/24", "requests": 0}]).source_policies
        self.assertFalse(is_trusted_rate_limit_source("198.51.100.9", (), policies))

    def test_loopback_rule_dropped_without_trusted_proxy(self):
        policies = _rate_limit(source_policies=[
            {"network": "127.0.0.1/32", "requests": 0, "trusted": True},
            {"network": "100.64.0.0/10", "requests": 0},
        ]).source_policies
        kept = effective_source_policies(policies, trusted_proxy_enabled=False)
        self.assertEqual([p.network for p in kept], ["100.64.0.0/10"])
        self.assertEqual(len(effective_source_policies(policies, trusted_proxy_enabled=True)), 2)


class TestValidation(unittest.TestCase):
    def _errors(self, rate_limit):
        config = parse_waf_config({"rate_limit": rate_limit, "rules": {"paths": ["x.json"]}})
        return validate_waf_config(config)

    def test_valid_rules(self):
        self.assertEqual(self._errors({
            "path_policies": [{"prefix": "/shots/", "requests": 0}],
            "source_policies": [{"network": "100.64.0.0/10", "requests": 10, "trusted": True}],
        }), [])

    def test_invalid_prefix_network_and_values(self):
        errors = self._errors({
            "path_policies": [{"prefix": "shots", "requests": -1, "window_seconds": 0}],
            "source_policies": [{"network": "pas-un-reseau", "requests": 1}],
        })
        self.assertEqual(len(errors), 4)


class TestPipeline(unittest.IsolatedAsyncioTestCase):
    async def _run(self, config, ip="203.0.113.1", path="/", rate=None, waf=None):
        return await evaluate_waf_request(
            _request(remote_ip=ip, path=path), config, waf or _FakeWafPort(_ALLOW), _FakeBlocklist(),
            rate or _CountingRateLimit(), _FakeReputationTracker(),
        )

    async def test_page_with_130_screenshots_passes_with_folder_rule(self):
        config = parse_waf_config({"rate_limit": {
            "enabled": True, "path_policies": [{"prefix": "/omega-serv/screenshots/", "requests": 600}],
        }})
        rate = _CountingRateLimit()
        await self._run(config, path="/omega-serv/", rate=rate)
        for i in range(130):
            decision = await self._run(config, path=f"/omega-serv/screenshots/{i}.png", rate=rate)
            self.assertEqual(decision.action, "allow")
        self.assertEqual(rate.counts["203.0.113.1"], 1)  # le global n'est pas entame

    async def test_global_still_applies_elsewhere(self):
        config = parse_waf_config({"rate_limit": {"enabled": True, "global": {"requests": 2}}})
        rate = _CountingRateLimit()
        await self._run(config, rate=rate)
        await self._run(config, rate=rate)
        decision = await self._run(config, rate=rate)
        self.assertEqual((decision.action, decision.status_code), ("block", 429))
        self.assertFalse(decision.throttle_only)

    async def test_unlimited_rule_never_counts(self):
        config = parse_waf_config({"rate_limit": {
            "enabled": True, "source_policies": [{"network": "203.0.113.0/24", "requests": 0}],
        }})
        rate = _CountingRateLimit()
        for _ in range(200):
            self.assertEqual((await self._run(config, rate=rate)).action, "allow")
        self.assertEqual(rate.counts, {})

    async def test_trusted_source_rejection_is_throttle_only(self):
        config = parse_waf_config({"rate_limit": {"enabled": True, "global": {"requests": 1}}})
        rate = _CountingRateLimit()
        await self._run(config, ip="100.100.1.2", rate=rate)
        decision = await self._run(config, ip="100.100.1.2", rate=rate)
        self.assertEqual((decision.action, decision.status_code), ("block", 429))
        self.assertTrue(decision.throttle_only)

    async def test_folder_rule_exceeded_by_public_ip_stays_bannable(self):
        config = parse_waf_config({"rate_limit": {
            "enabled": True, "path_policies": [{"prefix": "/shots", "requests": 1}],
        }})
        rate = _CountingRateLimit()
        await self._run(config, path="/shots/a", rate=rate)
        decision = await self._run(config, path="/shots/b", rate=rate)
        self.assertEqual(decision.action, "block")
        self.assertFalse(decision.throttle_only)
        self.assertIn("/shots", decision.blocked_reason)

    async def test_rate_rule_never_disables_inspection(self):
        block = _FakeWafPort(_ALLOW)
        config = parse_waf_config({"rate_limit": {
            "enabled": True, "path_policies": [{"prefix": "/shots", "requests": 0}],
        }})
        await self._run(config, path="/shots/../.env", waf=block)
        self.assertEqual(len(block.inspected_requests), 1)


class TestJailContract(unittest.TestCase):
    """La jail omega-jail `omega-serv-waf-block` (catalog.yaml) bannit sur
    `"action": "block"` : une ligne publique doit toujours matcher (D3),
    une ligne de source sure jamais (D4)."""
    JAIL_REGEX = re.compile(r'"remote_ip": "(?P<host>[^"]+)".*"action": "block"')

    def _line(self, throttle_only):
        from omega_serv.domain.security.waf.entities import WafDecision
        decision = WafDecision(action="block", status_code=429, score=0, throttle_only=throttle_only)
        entry = WafAlertEntry(
            request_id="r1", timestamp=datetime(2026, 10, 25, tzinfo=timezone.utc), remote_ip="203.0.113.1",
            method="GET", path="/", user_agent=None, decision=decision, duration_ms=0.1,
        )
        return format_waf_alert_line(entry, WafLoggingConfig())

    def test_public_rejection_still_matches_jail(self):
        self.assertIsNotNone(self.JAIL_REGEX.search(self._line(False)))

    def test_trusted_rejection_never_matches_jail(self):
        line = self._line(True)
        self.assertIsNone(self.JAIL_REGEX.search(line))
        self.assertIn('"action": "throttle"', line)


if __name__ == "__main__":
    unittest.main()
