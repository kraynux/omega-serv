"""Lecture des journaux en evenements RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.2-3.3, §3.9)."""
import json
import unittest

from omega_serv.domain.security.riposte.events import (
    parse_security_event_line,
    parse_waf_alert_line,
)


def _waf(**overrides):
    record = {
        "timestamp": "2026-11-01T10:00:00+00:00", "request_id": "r1", "remote_ip": "203.0.113.7",
        "method": "GET", "path": "/x", "user_agent": "curl", "action": "block", "stage": "inspection",
        "status_code": 403, "score": 8, "rules": ["SQLI-1"], "findings": [{"id": "SQLI-1", "pack": "body-sqli"}],
    }
    record.update(overrides)
    return json.dumps(record)


def _security(**overrides):
    record = {
        "schema_version": 1, "event_id": "e1", "type": "threat_escalated",
        "timestamp": "2026-11-01T10:00:00+00:00", "subject_id": "203.0.113.7:abcd", "remote_ip": "203.0.113.7",
        "level": "hostile", "previous_level": "suspicious", "score": 40, "attack_class": "sqli",
    }
    record.update(overrides)
    return json.dumps(record)


class TestWafAlertLines(unittest.TestCase):
    def test_attack_with_the_active_defense_classification(self):
        event = parse_waf_alert_line(_waf()).event
        self.assertEqual(event.kind, "attack")
        self.assertEqual(event.event_id, "waf:r1")
        self.assertEqual(event.attack_class, "sqli")  # meme heuristique qu'Active Defense
        self.assertEqual(event.rules, ("SQLI-1",))

    def test_blocklist_hit_is_never_an_attack(self):
        event = parse_waf_alert_line(_waf(stage="blocklist", score=0, rules=[], findings=[])).event
        self.assertEqual(event.kind, "blocklist_hit")
        self.assertIsNone(event.attack_class)

    def test_rate_limit_and_zero_score_are_not_attacks(self):
        self.assertEqual(parse_waf_alert_line(_waf(stage="rate_limit", score=0)).event.kind, "rate_limited")
        self.assertEqual(parse_waf_alert_line(_waf(score=0, findings=[], rules=[])).event.kind, "rate_limited")

    def test_line_without_stage_from_before_lot_1_is_read_as_inspection(self):
        record = json.loads(_waf())
        del record["stage"]
        self.assertEqual(parse_waf_alert_line(json.dumps(record)).event.kind, "attack")

    def test_unknown_pack_gives_unknown_class(self):
        self.assertEqual(parse_waf_alert_line(_waf(findings=[{"id": "X", "pack": "maison"}])).event.attack_class, "unknown")

    def test_rejections_carry_a_reason_and_never_raise(self):
        cases = {
            "": "empty", "pas du json": "not_json", "[1, 2]": "bad_schema",
            _waf(remote_ip="pas-une-ip"): "bad_ip", _waf(timestamp="hier"): "bad_timestamp",
            _waf(request_id=""): "bad_schema", _waf(score="8"): "bad_schema", _waf(score=True): "bad_schema",
            "{" + "x" * 70000 + "}": "too_long",
        }
        for line, reason in cases.items():
            result = parse_waf_alert_line(line)
            self.assertIsNone(result.event, line[:40])
            self.assertEqual(result.rejected_reason, reason, line[:40])

    def test_ipv6_is_normalized(self):
        self.assertEqual(parse_waf_alert_line(_waf(remote_ip="2001:DB8::0:1")).event.remote_ip, "2001:db8::1")


class TestSecurityEventLines(unittest.TestCase):
    def test_escalation(self):
        event = parse_security_event_line(_security()).event
        self.assertEqual((event.kind, event.event_id, event.level), ("threat_escalated", "security:e1", "hostile"))
        self.assertEqual(event.subject_id, "203.0.113.7:abcd")

    def test_decoy_hit(self):
        event = parse_security_event_line(_security(type="decoy_hit", decoy_profile="fake_admin", level=None)).event
        self.assertEqual((event.kind, event.decoy_profile), ("decoy_hit", "fake_admin"))

    def test_unknown_schema_or_type_is_rejected(self):
        self.assertEqual(parse_security_event_line(_security(schema_version=2)).rejected_reason, "bad_schema")
        self.assertEqual(parse_security_event_line(_security(type="pirate")).rejected_reason, "unknown_type")

    def test_event_ids_of_both_journals_never_collide(self):
        waf = parse_waf_alert_line(_waf(request_id="same")).event
        security = parse_security_event_line(_security(event_id="same")).event
        self.assertNotEqual(waf.event_id, security.event_id)


if __name__ == "__main__":
    unittest.main()
