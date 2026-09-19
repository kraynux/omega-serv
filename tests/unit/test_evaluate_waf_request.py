import unittest

from omega_serv.application.security.evaluate_waf_request import evaluate_waf_request
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.entities import (
    BlocklistEntry,
    Severity,
    WafDecision,
    WafFinding,
)
from omega_serv.ports.rate_limit_port import RateLimitCheckResult


class _FakeBlocklist:
    def __init__(self, blocked_entry=None):
        self._blocked_entry = blocked_entry
        self.auto_entries = []

    def is_blocked(self, ip):
        return self._blocked_entry

    def list_entries(self):
        return tuple(self.auto_entries)

    def add_entry(self, entry):
        self.auto_entries.append(entry)

    def remove_entry(self, network):
        return False

    def purge_expired(self):
        return 0

    def count_auto_entries(self):
        return len(self.auto_entries)


class _FakeRateLimit:
    def __init__(self, allowed=True):
        self._allowed = allowed

    def check(self, key, requests, window_seconds):
        return RateLimitCheckResult(allowed=self._allowed, retry_after_seconds=None if self._allowed else 30)

    def reset(self, key=None):
        pass


class _FakeWafPort:
    def __init__(self, decision: WafDecision):
        self._decision = decision

    def inspect(self, request):
        return self._decision


class _FakeReputationTracker:
    def __init__(self, hit_count=0):
        self.hits = []
        self._hit_count = hit_count

    def record_hit(self, ip):
        self.hits.append(ip)

    def count_hits_in_window(self, ip, window_seconds):
        return self._hit_count

    def reset(self, ip=None):
        pass


def _request(remote_ip="203.0.113.1", path="/") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip=remote_ip, peer_ip=remote_ip, method="GET",
        path=path, raw_path=path, query="", headers=HttpHeaders.from_pairs([]),
        body=None, content_length=None, is_tls=False,
    )


_ALLOW = WafDecision(action="allow", status_code=None, score=0)
_LOG_WITH_FINDING = WafDecision(
    action="log", status_code=None, score=3,
    findings=(WafFinding(rule_id="R1", pack="p", description="", severity=Severity.MEDIUM, weight=3, scope="query"),),
)


class TestEvaluateWafRequest(unittest.TestCase):
    def test_blocked_ip_short_circuits_everything(self):
        entry = BlocklistEntry(network="203.0.113.1/32", reason="banni", created_at="2026-09-05T00:00:00+00:00")
        decision = evaluate_waf_request(
            _request(), parse_waf_config({}), _FakeWafPort(_ALLOW), _FakeBlocklist(entry),
            _FakeRateLimit(), _FakeReputationTracker(),
        )
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 403)

    def test_rate_limit_exceeded_blocks_before_waf_inspection(self):
        decision = evaluate_waf_request(
            _request(), parse_waf_config({"rate_limit": {"enabled": True}}), _FakeWafPort(_ALLOW),
            _FakeBlocklist(), _FakeRateLimit(allowed=False), _FakeReputationTracker(),
        )
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 429)
        self.assertIsNotNone(decision.retry_after_seconds)

    def test_excluded_path_skips_waf_inspection(self):
        config = parse_waf_config({"exclusions": {"path_prefixes": ["/healthz"]}})
        waf_port = _FakeWafPort(WafDecision(action="block", status_code=403, score=99))  # ne doit jamais etre consulte pour la decision finale
        decision = evaluate_waf_request(
            _request(path="/healthz"), config, waf_port, _FakeBlocklist(), _FakeRateLimit(), _FakeReputationTracker(),
        )
        self.assertEqual(decision.action, "allow")

    def test_clean_request_allowed(self):
        decision = evaluate_waf_request(
            _request(), parse_waf_config({}), _FakeWafPort(_ALLOW), _FakeBlocklist(),
            _FakeRateLimit(), _FakeReputationTracker(),
        )
        self.assertEqual(decision.action, "allow")

    def test_finding_records_reputation_hit(self):
        tracker = _FakeReputationTracker()
        config = parse_waf_config({"reputation": {"enabled": True}})
        evaluate_waf_request(
            _request(), config, _FakeWafPort(_LOG_WITH_FINDING), _FakeBlocklist(),
            _FakeRateLimit(), tracker,
        )
        self.assertEqual(tracker.hits, ["203.0.113.1"])

    def test_no_finding_does_not_record_reputation_hit(self):
        tracker = _FakeReputationTracker()
        config = parse_waf_config({"reputation": {"enabled": True}})
        evaluate_waf_request(
            _request(), config, _FakeWafPort(_ALLOW), _FakeBlocklist(),
            _FakeRateLimit(), tracker,
        )
        self.assertEqual(tracker.hits, [])

    def test_escalation_triggers_auto_block_when_enabled(self):
        blocklist = _FakeBlocklist()
        tracker = _FakeReputationTracker(hit_count=5)
        config = parse_waf_config({
            "reputation": {"enabled": True, "suspicious_threshold": 3, "auto_block": True, "auto_block_max_entries": 10},
        })
        evaluate_waf_request(
            _request(), config, _FakeWafPort(_LOG_WITH_FINDING), blocklist, _FakeRateLimit(), tracker,
        )
        self.assertEqual(len(blocklist.auto_entries), 1)
        self.assertEqual(blocklist.auto_entries[0].source, "auto")

    def test_escalation_does_not_auto_block_when_disabled(self):
        blocklist = _FakeBlocklist()
        tracker = _FakeReputationTracker(hit_count=5)
        config = parse_waf_config({
            "reputation": {"enabled": True, "suspicious_threshold": 3, "auto_block": False},
        })
        evaluate_waf_request(
            _request(), config, _FakeWafPort(_LOG_WITH_FINDING), blocklist, _FakeRateLimit(), tracker,
        )
        self.assertEqual(len(blocklist.auto_entries), 0)

    def test_auto_block_respects_max_entries_cap(self):
        blocklist = _FakeBlocklist()
        blocklist.auto_entries = [
            BlocklistEntry(network=f"203.0.113.{i}/32", reason="x", created_at="2026-09-05T00:00:00+00:00", source="auto")
            for i in range(2)
        ]
        tracker = _FakeReputationTracker(hit_count=5)
        config = parse_waf_config({
            "reputation": {"enabled": True, "suspicious_threshold": 3, "auto_block": True, "auto_block_max_entries": 2},
        })
        evaluate_waf_request(
            _request(), config, _FakeWafPort(_LOG_WITH_FINDING), blocklist, _FakeRateLimit(), tracker,
        )
        self.assertEqual(len(blocklist.auto_entries), 2)  # plafond deja atteint, aucun ajout


if __name__ == "__main__":
    unittest.main()
