# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.security.waf.config import ScoringConfig
from omega_serv.domain.security.waf.entities import Severity, WafFinding
from omega_serv.domain.security.waf.scoring import compute_decision

_SCORING = ScoringConfig(block_threshold=5, high_score_threshold=8, response_status=403)


def _finding(weight: int) -> WafFinding:
    return WafFinding(rule_id="R1", pack="p", description="", severity=Severity.HIGH, weight=weight, scope="query")


class TestComputeDecision(unittest.TestCase):
    def test_no_findings_allows(self):
        decision = compute_decision((), _SCORING, mode="block")
        self.assertEqual(decision.action, "allow")
        self.assertEqual(decision.score, 0)

    def test_below_threshold_logs_only(self):
        decision = compute_decision((_finding(2),), _SCORING, mode="block")
        self.assertEqual(decision.action, "log")
        self.assertEqual(decision.score, 2)

    def test_above_threshold_blocks_in_block_mode(self):
        decision = compute_decision((_finding(5),), _SCORING, mode="block")
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 403)

    def test_above_threshold_never_blocks_in_log_only_mode(self):
        decision = compute_decision((_finding(10),), _SCORING, mode="log-only")
        self.assertEqual(decision.action, "log")
        self.assertIsNone(decision.status_code)

    def test_high_score_raises_log_level_to_critical(self):
        decision = compute_decision((_finding(10),), _SCORING, mode="log-only")
        self.assertEqual(decision.log_level, "critical")

    def test_score_sums_multiple_findings(self):
        decision = compute_decision((_finding(2), _finding(2)), _SCORING, mode="block")
        self.assertEqual(decision.score, 4)
        self.assertEqual(decision.action, "log")  # 4 < 5


if __name__ == "__main__":
    unittest.main()
