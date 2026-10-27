"""Rejets de VOLUME renvoyes par le script magnet (decisions utilisateur
2026-10-26, cas reel craftdark : une page de ~130 captures en 4G faisait
bannir le visiteur par la reputation native, chaque 429 du script devenant
un finding "magnet-external").

- 429/413/414 de magnet : aucun finding -> jamais une detection suspecte ;
- 429 sur une requete couverte par une regle de debit native explicite : le
  natif fait foi, le 429 de magnet est ignore ;
- source sure -> journalise "throttle" ; IP publique -> "block" (jail
  omega-jail inchangee, D3) ;
- un 403/451 de magnet reste une detection."""
import re
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from omega_serv.application.security.evaluate_waf_request import evaluate_waf_request
from omega_serv.domain.logging.waf_alert_format import WafAlertEntry, format_waf_alert_line
from omega_serv.domain.security.waf.config import WafLoggingConfig, parse_waf_config
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.infrastructure.waf.lua_waf_adapter import LuaWafAdapter
from tests.unit.test_evaluate_waf_request import (
    _ALLOW,
    _FakeBlocklist,
    _FakeRateLimit,
    _FakeReputationTracker,
    _FakeWafPort,
    _request,
)

_PATHS = {"blocklist_file": "", "rules_dir": "", "alerts_log": "", "blocklist_log": "", "rate_store_file": ""}
_JAIL_REGEX = re.compile(r'"remote_ip": "(?P<host>[^"]+)".*"action": "block"')


def _settings(**rate_limit):
    settings = {"mode": "block", "magnet": {"enabled": True, "script": "x.lua"},
                "reputation": {"enabled": True, "auto_block": True, "suspicious_threshold": 1}}
    if rate_limit:
        settings["rate_limit"] = rate_limit
    return settings


class TestMagnetVolumeRejections(unittest.IsolatedAsyncioTestCase):
    async def _evaluate(self, code, settings, ip="203.0.113.1", path="/omega-serv/screenshots/a.png"):
        waf_config = parse_waf_config(settings)
        magnet = LuaWafAdapter(f"return {code}", waf_config, _PATHS)
        self.blocklist = _FakeBlocklist()
        self.reputation = _FakeReputationTracker(hit_count=99)
        return await evaluate_waf_request(
            _request(remote_ip=ip, path=path), waf_config, _FakeWafPort(_ALLOW), self.blocklist,
            _FakeRateLimit(), self.reputation, magnet_port=magnet,
        )

    def _log_line(self, decision, ip="203.0.113.1"):
        entry = WafAlertEntry(
            request_id="r1", timestamp=datetime(2026, 10, 26, tzinfo=timezone.utc), remote_ip=ip,
            method="GET", path="/", user_agent=None, decision=decision, duration_ms=0.1,
        )
        return format_waf_alert_line(entry, WafLoggingConfig())

    async def test_magnet_429_is_a_rejection_never_a_detection(self):
        for code in (429, 413, 414):
            decision = await self._evaluate(code, _settings())
            self.assertEqual((decision.action, decision.status_code), ("block", code))
            self.assertEqual(decision.findings, ())
            self.assertEqual(self.reputation.hits, [], code)
            self.assertEqual(self.blocklist.auto_entries, [], code)

    async def test_public_magnet_429_stays_bannable_by_the_jail(self):
        decision = await self._evaluate(429, _settings())
        self.assertIsNotNone(_JAIL_REGEX.search(self._log_line(decision)))

    async def test_trusted_source_magnet_429_is_logged_throttle(self):
        decision = await self._evaluate(429, _settings(), ip="100.101.102.103")
        self.assertEqual(decision.status_code, 429)
        line = self._log_line(decision, ip="100.101.102.103")
        self.assertIsNone(_JAIL_REGEX.search(line))
        self.assertIn('"action": "throttle"', line)

    async def test_native_folder_rule_overrides_magnet_429(self):
        settings = _settings(enabled=True, path_policies=[{"prefix": "/omega-serv/screenshots/", "requests": 600}])
        decision = await self._evaluate(429, settings)
        self.assertEqual(decision.action, "allow")

    async def test_native_source_rule_overrides_magnet_429(self):
        settings = _settings(enabled=True, source_policies=[{"network": "203.0.113.0/24", "requests": 600}])
        decision = await self._evaluate(429, settings)
        self.assertEqual(decision.action, "allow")

    async def test_global_only_or_disabled_native_rate_limit_keeps_magnet_429(self):
        for settings in (_settings(enabled=True), _settings(enabled=False, path_policies=[
            {"prefix": "/omega-serv/screenshots/", "requests": 600},
        ])):
            decision = await self._evaluate(429, settings)
            self.assertEqual(decision.status_code, 429)

    async def test_native_rule_never_overrides_magnet_signatures(self):
        settings = _settings(enabled=True, path_policies=[{"prefix": "/omega-serv/screenshots/", "requests": 0}])
        decision = await self._evaluate(403, settings)
        self.assertEqual((decision.action, decision.status_code), ("block", 403))
        self.assertEqual([f.rule_id for f in decision.findings], ["magnet-external"])
        self.assertEqual(self.reputation.hits, ["203.0.113.1"])

    async def test_native_rule_does_not_override_size_rejections(self):
        settings = _settings(enabled=True, path_policies=[{"prefix": "/omega-serv/screenshots/", "requests": 600}])
        decision = await self._evaluate(413, settings)
        self.assertEqual(decision.status_code, 413)


class TestErrorCssServedToBlockedClients(unittest.IsolatedAsyncioTestCase):
    """Decision utilisateur 2026-10-26 (retour n° 3) : la feuille de style des
    pages d'erreur reste servie a une IP bloquee ou limitee - et seulement elle."""

    async def _evaluate(self, path, method="GET"):
        entry = BlocklistEntry(network="203.0.113.1/32", reason="banni", created_at="2026-10-26T00:00:00+00:00")
        request = replace(_request(path=path), method=method)
        return await evaluate_waf_request(
            request, parse_waf_config({"mode": "block", "rate_limit": {"enabled": True}}),
            _FakeWafPort(_ALLOW), _FakeBlocklist(entry), _FakeRateLimit(allowed=False), _FakeReputationTracker(),
        )

    async def test_error_css_passes_the_blocklist(self):
        decision = await self._evaluate("/.omega-serv-error-css/error-pages.css")
        self.assertEqual(decision.action, "allow")

    async def test_anything_else_stays_blocked(self):
        for path, method in (
            ("/favicon.ico", "GET"), ("/.omega-serv-error-css/autre.css", "GET"),
            ("/.omega-serv-error-css/error-pages.css", "POST"), ("/.omega-serv-error-css/error-pages.css/x", "GET"),
        ):
            decision = await self._evaluate(path, method)
            self.assertEqual(decision.action, "block", path)


if __name__ == "__main__":
    unittest.main()
