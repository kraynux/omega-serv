"""Journal des evenements de securite (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md, lot 1) : contrat machine
lu par RIPOSTE - schema versionne, champs absents omis, jamais d'injection de ligne."""
import json
import unittest
from datetime import datetime, timezone

from omega_serv.domain.logging.security_event_format import (
    SECURITY_EVENT_TYPES,
    SECURITY_EVENTS_SCHEMA_VERSION,
    SecurityEvent,
    format_security_event_line,
)

_NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _event(**overrides):
    values = {
        "event_id": "e1", "type": "threat_escalated", "timestamp": _NOW,
        "subject_id": "203.0.113.1:abcd", "remote_ip": "203.0.113.1",
    }
    values.update(overrides)
    return SecurityEvent(**values)


class TestFormatSecurityEventLine(unittest.TestCase):
    def test_mandatory_fields_and_schema_version(self):
        record = json.loads(format_security_event_line(_event()))
        self.assertEqual(record["schema_version"], SECURITY_EVENTS_SCHEMA_VERSION)
        self.assertEqual(record["event_id"], "e1")
        self.assertEqual(record["type"], "threat_escalated")
        self.assertEqual(record["timestamp"], _NOW.isoformat())
        self.assertEqual(record["remote_ip"], "203.0.113.1")

    def test_absent_fields_are_omitted_not_null(self):
        record = json.loads(format_security_event_line(_event()))
        for key in ("level", "previous_level", "score", "attack_class", "incident_id", "decoy_profile"):
            self.assertNotIn(key, record)

    def test_escalation_fields(self):
        record = json.loads(format_security_event_line(
            _event(level="hostile", previous_level="suspicious", score=0, attack_class="sqli"),
        ))
        self.assertEqual((record["level"], record["previous_level"]), ("hostile", "suspicious"))
        self.assertEqual(record["score"], 0)  # 0 est une valeur, jamais omise
        self.assertEqual(record["attack_class"], "sqli")

    def test_one_physical_line_even_with_control_characters(self):
        line = format_security_event_line(_event(subject_id="x\ny", decoy_profile="a\r\nb"))
        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)

    def test_known_types(self):
        self.assertEqual(SECURITY_EVENT_TYPES, {"threat_escalated", "incident_opened", "deception_assigned", "decoy_hit"})


if __name__ == "__main__":
    unittest.main()
