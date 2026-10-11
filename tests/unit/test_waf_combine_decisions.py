import unittest

from omega_serv.domain.security.waf.combine_decisions import (
    combine_decisions,
    magnet_fallback_decision,
)
from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding

_ALLOW = WafDecision(action="allow", status_code=None, score=0, log_level="debug")
_LOG = WafDecision(action="log", status_code=None, score=3, log_level="info")
_BLOCK = WafDecision(action="block", status_code=403, score=5, log_level="warning", blocked_reason="x")


class TestCombineDecisions(unittest.TestCase):
    def test_magnet_none_returns_native_unchanged(self):
        self.assertIs(combine_decisions(_BLOCK, None), _BLOCK)

    def test_native_allow_magnet_allow_stays_allow(self):
        result = combine_decisions(_ALLOW, _ALLOW)
        self.assertEqual(result.action, "allow")

    def test_native_block_magnet_allow_still_blocks(self):
        """Le magnet ne peut JAMAIS lever un blocage decide par le natif."""
        result = combine_decisions(_BLOCK, _ALLOW)
        self.assertEqual(result.action, "block")
        self.assertEqual(result.status_code, 403)

    def test_native_allow_magnet_block_now_blocks(self):
        result = combine_decisions(_ALLOW, _BLOCK)
        self.assertEqual(result.action, "block")
        self.assertEqual(result.status_code, 403)

    def test_native_log_magnet_block_blocks(self):
        result = combine_decisions(_LOG, _BLOCK)
        self.assertEqual(result.action, "block")

    def test_native_block_magnet_log_still_blocks(self):
        result = combine_decisions(_BLOCK, _LOG)
        self.assertEqual(result.action, "block")

    def test_native_log_magnet_allow_stays_log(self):
        result = combine_decisions(_LOG, _ALLOW)
        self.assertEqual(result.action, "log")

    def test_native_allow_magnet_log_becomes_log(self):
        result = combine_decisions(_ALLOW, _LOG)
        self.assertEqual(result.action, "log")

    def test_both_block_stays_block(self):
        result = combine_decisions(_BLOCK, _BLOCK)
        self.assertEqual(result.action, "block")

    def test_scores_are_summed(self):
        result = combine_decisions(_LOG, _BLOCK)
        self.assertEqual(result.score, _LOG.score + _BLOCK.score)

    def test_findings_are_concatenated_and_attributed(self):
        native_finding = WafFinding(rule_id="SQLI-001", pack="body-sqli", description="", severity=Severity.HIGH, weight=5, scope="query")
        magnet_finding = WafFinding(rule_id="MAGNET-001", pack="magnet", description="", severity=Severity.HIGH, weight=5, scope="path")
        native = WafDecision(action="log", status_code=None, score=5, findings=(native_finding,), log_level="info")
        magnet = WafDecision(action="block", status_code=403, score=5, findings=(magnet_finding,), log_level="warning")
        result = combine_decisions(native, magnet)
        self.assertEqual(result.findings, (native_finding, magnet_finding))
        self.assertEqual({f.pack for f in result.findings}, {"body-sqli", "magnet"})


class TestMagnetFallbackDecision(unittest.TestCase):
    def test_ignore_is_neutral_allow(self):
        decision = magnet_fallback_decision("ignore", mode="block")
        self.assertEqual(decision.action, "allow")

    def test_fail_closed_blocks_when_mode_is_block(self):
        decision = magnet_fallback_decision("fail-closed", mode="block")
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 503)

    def test_fail_closed_never_blocks_in_log_only_mode(self):
        """Invariant central du WAF (scoring.py, decision #14) : log-only
        ne bloque JAMAIS, meme si le magnet est en fail-closed."""
        decision = magnet_fallback_decision("fail-closed", mode="log-only")
        self.assertEqual(decision.action, "log")


if __name__ == "__main__":
    unittest.main()
