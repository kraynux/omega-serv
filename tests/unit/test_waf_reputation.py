# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.security.waf.reputation import evaluate_escalation


class TestEvaluateEscalation(unittest.TestCase):
    def test_below_threshold_does_not_escalate(self):
        decision = evaluate_escalation(hit_count_in_window=2, suspicious_threshold=3)
        self.assertFalse(decision.should_escalate)

    def test_at_threshold_escalates(self):
        decision = evaluate_escalation(hit_count_in_window=3, suspicious_threshold=3)
        self.assertTrue(decision.should_escalate)

    def test_above_threshold_escalates(self):
        decision = evaluate_escalation(hit_count_in_window=10, suspicious_threshold=3)
        self.assertTrue(decision.should_escalate)

    def test_disabled_threshold_never_escalates(self):
        decision = evaluate_escalation(hit_count_in_window=999, suspicious_threshold=0)
        self.assertFalse(decision.should_escalate)


if __name__ == "__main__":
    unittest.main()
