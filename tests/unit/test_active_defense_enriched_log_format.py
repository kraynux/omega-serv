"""plan_active_defense_omega_serv.md, Phase 4, action "enrich_log" -
format_enriched_log_line() est une fonction pure (aucune I/O), meme
discipline que test_waf_alert_format.py (mais pas encore de tel fichier
pour le WAF - conventions calquees sur format_waf_alert_line lui-meme)."""
import json
import unittest
from datetime import datetime, timezone

from omega_serv.domain.logging.active_defense_enriched_log_format import (
    EnrichedLogEntry,
    format_enriched_log_line,
)
from omega_serv.domain.security.active_defense.config import ActiveDefenseLoggingConfig
from omega_serv.domain.security.active_defense.policies import hash_payload

_NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)


def _entry(**overrides) -> EnrichedLogEntry:
    defaults = {
        "timestamp": _NOW,
        "subject_id": "203.0.113.1:abcd1234",
        "remote_ip": "203.0.113.1",
        "method": "GET",
        "path": "/wp-login.php",
        "user_agent": "curl/8.0",
        "score": 65,
        "level": "hostile",
        "attack_class": "scan",
        "headers": {"authorization": "Bearer secret-token", "x-custom": "value"},
    }
    defaults.update(overrides)
    return EnrichedLogEntry(**defaults)


class TestFormatEnrichedLogLine(unittest.TestCase):
    def test_produces_valid_json(self):
        line = format_enriched_log_line(_entry(), ActiveDefenseLoggingConfig())
        record = json.loads(line)
        self.assertEqual(record["subject_id"], "203.0.113.1:abcd1234")
        self.assertEqual(record["score"], 65)
        self.assertEqual(record["level"], "hostile")
        self.assertEqual(record["attack_class"], "scan")

    def test_redacts_configured_header_fields(self):
        line = format_enriched_log_line(_entry(), ActiveDefenseLoggingConfig())
        record = json.loads(line)
        self.assertEqual(record["headers"]["authorization"], "***REDACTED***")
        self.assertEqual(record["headers"]["x-custom"], "value")
        self.assertNotIn("secret-token", line)

    def test_body_is_hashed_when_capture_request_body_is_false(self):
        config = ActiveDefenseLoggingConfig(capture_request_body=False)
        line = format_enriched_log_line(_entry(body=b"payload=secret"), config)
        record = json.loads(line)
        self.assertNotIn("body_excerpt", record)
        self.assertEqual(record["body_sha256"], hash_payload(b"payload=secret"))
        self.assertNotIn("secret", line.replace(record["body_sha256"], ""))

    def test_body_excerpt_included_and_truncated_when_capture_request_body_is_true(self):
        config = ActiveDefenseLoggingConfig(capture_request_body=True, max_body_bytes=5)
        line = format_enriched_log_line(_entry(body=b"0123456789"), config)
        record = json.loads(line)
        self.assertEqual(record["body_excerpt"], "01234")
        self.assertNotIn("body_sha256", record)

    def test_no_body_field_when_body_is_none(self):
        line = format_enriched_log_line(_entry(body=None), ActiveDefenseLoggingConfig())
        record = json.loads(line)
        self.assertNotIn("body_excerpt", record)
        self.assertNotIn("body_sha256", record)

    def test_password_field_in_captured_body_is_redacted(self):
        config = ActiveDefenseLoggingConfig(capture_request_body=True)
        line = format_enriched_log_line(_entry(body=b"username=admin&password=Secret123"), config)
        record = json.loads(line)
        self.assertNotIn("Secret123", line)
        self.assertIn("username=admin", record["body_excerpt"])
        self.assertIn("REDACTED", record["body_excerpt"])

    def test_non_form_body_is_left_unredacted(self):
        config = ActiveDefenseLoggingConfig(capture_request_body=True)
        line = format_enriched_log_line(_entry(body=b'{"hello":"world"}'), config)
        record = json.loads(line)
        self.assertIn("hello", record["body_excerpt"])

    def test_no_user_agent_field_when_absent(self):
        line = format_enriched_log_line(_entry(user_agent=None), ActiveDefenseLoggingConfig())
        record = json.loads(line)
        self.assertIsNone(record["user_agent"])


if __name__ == "__main__":
    unittest.main()
