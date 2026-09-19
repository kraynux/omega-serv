import unittest
from datetime import datetime, timezone

from omega_serv.domain.security.audit.entities import (
    AuditFinding,
    AuditResult,
    Severity,
    severity_at_least,
)


def _finding(severity: Severity, rule_id: str = "X-1") -> AuditFinding:
    return AuditFinding(
        rule_id=rule_id, rule_name="test", severity=severity, category="test",
        message="msg", recommendation="fix it",
    )


class TestSeverityAtLeast(unittest.TestCase):
    def test_critical_is_at_least_low(self):
        self.assertTrue(severity_at_least(Severity.CRITICAL, Severity.LOW))

    def test_low_is_not_at_least_critical(self):
        self.assertFalse(severity_at_least(Severity.LOW, Severity.CRITICAL))

    def test_same_severity_is_at_least_itself(self):
        self.assertTrue(severity_at_least(Severity.MEDIUM, Severity.MEDIUM))

    def test_low_is_at_least_info(self):
        self.assertTrue(severity_at_least(Severity.LOW, Severity.INFO))

    def test_info_is_not_at_least_low(self):
        self.assertFalse(severity_at_least(Severity.INFO, Severity.LOW))


class TestAuditResult(unittest.TestCase):
    def _result(self, *findings: AuditFinding) -> AuditResult:
        return AuditResult(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), config_path="c.json", findings=findings)

    def test_empty_findings_is_secure_with_exit_code_zero(self):
        result = self._result()
        self.assertTrue(result.is_secure)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.summary["critical"], 0)

    def test_critical_finding_forces_exit_code_one_and_insecure(self):
        result = self._result(_finding(Severity.CRITICAL))
        self.assertFalse(result.is_secure)
        self.assertEqual(result.exit_code, 1)

    def test_high_without_critical_gives_exit_code_two(self):
        result = self._result(_finding(Severity.HIGH))
        self.assertFalse(result.is_secure)
        self.assertEqual(result.exit_code, 2)

    def test_only_medium_or_below_is_secure_with_exit_code_zero(self):
        result = self._result(_finding(Severity.MEDIUM), _finding(Severity.LOW), _finding(Severity.INFO))
        self.assertTrue(result.is_secure)
        self.assertEqual(result.exit_code, 0)

    def test_summary_counts_each_severity(self):
        result = self._result(_finding(Severity.CRITICAL), _finding(Severity.CRITICAL), _finding(Severity.LOW))
        self.assertEqual(result.summary, {"critical": 2, "high": 0, "medium": 0, "low": 1, "info": 0})

    def test_to_dict_contains_all_findings(self):
        result = self._result(_finding(Severity.HIGH, rule_id="GEN-001"))
        payload = result.to_dict()
        self.assertEqual(len(payload["findings"]), 1)
        self.assertEqual(payload["findings"][0]["rule_id"], "GEN-001")
        self.assertFalse(payload["is_secure"])


if __name__ == "__main__":
    unittest.main()
