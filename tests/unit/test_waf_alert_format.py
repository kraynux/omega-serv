# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import json
import unittest
from datetime import datetime, timezone

from omega_serv.domain.logging.waf_alert_format import WafAlertEntry, format_waf_alert_line
from omega_serv.domain.security.waf.config import WafLoggingConfig
from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding

_NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def _entry(**overrides):
    decision = overrides.pop("decision", WafDecision(
        action="block", status_code=403, score=5,
        findings=(WafFinding(rule_id="SQLI-001", pack="body-sqli", description="", severity=Severity.HIGH, weight=5, scope="query"),),
        log_level="warning",
    ))
    defaults = {
        "request_id": "r1", "timestamp": _NOW, "remote_ip": "203.0.113.1", "method": "GET",
        "path": "/admin", "user_agent": "curl/8.0", "decision": decision, "duration_ms": 1.234,
    }
    defaults.update(overrides)
    return WafAlertEntry(**defaults)


class TestFormatWafAlertLine(unittest.TestCase):
    def test_produces_valid_json(self):
        line = format_waf_alert_line(_entry(), WafLoggingConfig())
        record = json.loads(line)
        self.assertEqual(record["action"], "block")
        self.assertEqual(record["rules"], ["SQLI-001"])
        self.assertEqual(record["score"], 5)

    def test_never_includes_body_by_default(self):
        line = format_waf_alert_line(_entry(body_excerpt="secret=1234"), WafLoggingConfig())
        self.assertNotIn("secret", line)

    def test_includes_body_excerpt_when_explicitly_enabled(self):
        config = WafLoggingConfig(include_body_excerpt=True, body_excerpt_max_bytes=100)
        line = format_waf_alert_line(_entry(body_excerpt="hello=world"), config)
        record = json.loads(line)
        self.assertEqual(record["body_excerpt"], "hello=world")

    def test_body_excerpt_truncated_to_configured_max(self):
        config = WafLoggingConfig(include_body_excerpt=True, body_excerpt_max_bytes=5)
        line = format_waf_alert_line(_entry(body_excerpt="0123456789"), config)
        record = json.loads(line)
        self.assertEqual(record["body_excerpt"], "01234")

    def test_password_field_in_body_excerpt_is_redacted(self):
        # Retour utilisateur (audit securite) : `WafFinding` ne
        # transporte jamais de texte brut par construction, mais
        # `body_excerpt` est un champ SEPARE qui, lui, journalisait le
        # corps verbatim - un POST /login inspecte par le WAF exposait
        # le mot de passe soumis en clair dans l'alerte.
        config = WafLoggingConfig(include_body_excerpt=True, body_excerpt_max_bytes=200)
        line = format_waf_alert_line(_entry(body_excerpt="username=admin&password=Secret123"), config)
        record = json.loads(line)
        self.assertNotIn("Secret123", line)
        self.assertIn("username=admin", record["body_excerpt"])
        self.assertIn("REDACTED", record["body_excerpt"])

    def test_path_truncated_to_configured_max(self):
        config = WafLoggingConfig(max_path_chars=5)
        line = format_waf_alert_line(_entry(path="/very/long/path"), config)
        record = json.loads(line)
        self.assertEqual(record["path"], "/very")

    def test_control_characters_in_path_neutralized(self):
        line = format_waf_alert_line(_entry(path="/a\r\nInjected: true"), WafLoggingConfig())
        self.assertNotIn("\r", line)
        self.assertNotIn("\n", line)

    def test_no_user_agent_is_null(self):
        line = format_waf_alert_line(_entry(user_agent=None), WafLoggingConfig())
        record = json.loads(line)
        self.assertIsNone(record["user_agent"])


if __name__ == "__main__":
    unittest.main()
