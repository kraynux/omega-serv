"""Exports STIX 2.1 et MISP d'un incident (OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §2,
decisions du 2026-10-26 : les deux formats, TLP:AMBER par defaut, identifiants stables, niveau de
menace MISP selon la confiance, fichiers locaux seulement)."""
import json
import re
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.security.active_defense.config import (
    IoCConfig,
    parse_active_defense_config,
    validate_active_defense_config,
)
from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentEvent,
    ThreatObservation,
)
from omega_serv.infrastructure.exporters.ioc_exporters import build_ioc_exporters
from omega_serv.infrastructure.exporters.misp_ioc_exporter import (
    build_misp_event,
    misp_threat_level,
)
from omega_serv.infrastructure.exporters.stix_ioc_exporter import (
    TLP_MARKING_DEFINITIONS,
    build_stix_bundle,
    stix_timestamp,
)
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

_NOW = datetime(2026, 10, 26, 12, 0, 0, 123456, tzinfo=timezone.utc)
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")


def _incident(ip: str = "203.0.113.7", score_delta: int = 80, status: str = "open") -> Incident:
    observations = tuple(
        ThreatObservation(subject_id=f"{ip}:abcd1234", observed_at=_NOW + timedelta(minutes=i), kind="waf_decision",
                          attack_class="recon", score_delta=score_delta, detail="WAF block")
        for i in range(2)
    )
    return Incident(
        incident_id="inc-1", subject_id=f"{ip}:abcd1234", status=status, opened_at=_NOW,
        closed_at=_NOW + timedelta(hours=1) if status == "closed" else None, observations=observations,
        events=(IncidentEvent(occurred_at=_NOW, kind="waf_decision", detail="WAF block"),),
    )


def _by_type(bundle: dict, kind: str) -> list[dict]:
    return [o for o in bundle["objects"] if o["type"] == kind]


class TestStixBundle(unittest.TestCase):
    def test_structure_pattern_marking_and_timestamps(self):
        bundle = build_stix_bundle(_incident(), "amber")
        self.assertEqual(bundle["type"], "bundle")
        self.assertTrue(bundle["id"].startswith("bundle--"))
        (indicator,) = _by_type(bundle, "indicator")
        self.assertEqual(indicator["spec_version"], "2.1")
        self.assertEqual(indicator["pattern"], "[ipv4-addr:value = '203.0.113.7']")
        self.assertEqual(indicator["pattern_type"], "stix")
        self.assertEqual(indicator["object_marking_refs"], [TLP_MARKING_DEFINITIONS["amber"]])
        self.assertEqual(indicator["indicator_types"], ["malicious-activity"])
        self.assertEqual(indicator["confidence"], 100)  # 2 x 80, borne a 100
        for key in ("created", "modified", "valid_from"):
            self.assertRegex(indicator[key], _TIMESTAMP)
        (report,) = _by_type(bundle, "report")
        self.assertEqual(report["object_refs"], [indicator["id"]])
        (marking,) = _by_type(bundle, "marking-definition")
        self.assertEqual((marking["id"], marking["definition"]), (TLP_MARKING_DEFINITIONS["amber"], {"tlp": "amber"}))
        (identity,) = _by_type(bundle, "identity")
        self.assertEqual((identity["name"], identity["identity_class"]), ("omega-serv", "system"))

    def test_ipv6_pattern(self):
        (indicator,) = _by_type(build_stix_bundle(_incident("2001:db8::7"), "amber"), "indicator")
        self.assertEqual(indicator["pattern"], "[ipv6-addr:value = '2001:db8::7']")

    def test_identifiers_are_stable_across_exports(self):
        self.assertEqual(build_stix_bundle(_incident(), "amber"), build_stix_bundle(_incident(), "amber"))

    def test_user_agent_hash_is_never_a_pattern(self):
        bundle = build_stix_bundle(_incident(), "amber")
        self.assertNotIn("abcd1234", json.dumps(bundle))

    def test_report_still_valid_without_shareable_indicator(self):
        empty = replace(_incident(), observations=())
        bundle = build_stix_bundle(empty, "red")
        (report,) = _by_type(bundle, "report")
        (identity,) = _by_type(bundle, "identity")
        self.assertEqual(report["object_refs"], [identity["id"]])
        self.assertEqual(report["object_marking_refs"], [TLP_MARKING_DEFINITIONS["red"]])

    def test_timestamp_format(self):
        self.assertEqual(stix_timestamp(_NOW), "2026-10-26T12:00:00.123Z")


class TestMispEvent(unittest.TestCase):
    def test_event_fields_attribute_and_tlp_tag(self):
        event = build_misp_event(_incident(), "amber", minimum_confidence=70)["Event"]
        self.assertEqual(event["distribution"], "0")
        self.assertEqual(event["analysis"], "0")
        self.assertFalse(event["published"])
        self.assertEqual(event["Tag"], [{"name": "tlp:amber"}])
        self.assertEqual(event["date"], "2026-10-26")
        (attribute,) = event["Attribute"]
        self.assertEqual((attribute["type"], attribute["category"], attribute["value"]),
                         ("ip-src", "Network activity", "203.0.113.7"))
        self.assertTrue(attribute["to_ids"])

    def test_to_ids_and_threat_level_follow_confidence(self):
        event = build_misp_event(_incident(score_delta=20), "green", minimum_confidence=70)["Event"]
        self.assertFalse(event["Attribute"][0]["to_ids"])  # confiance 40 < 70
        self.assertEqual(event["threat_level_id"], "3")
        self.assertEqual([misp_threat_level(c) for c in (95, 90, 70, 69)], ["1", "1", "2", "3"])

    def test_closed_incident_is_complete_analysis(self):
        self.assertEqual(build_misp_event(_incident(status="closed"), "amber", 70)["Event"]["analysis"], "2")

    def test_stable_uuids(self):
        self.assertEqual(build_misp_event(_incident(), "amber", 70), build_misp_event(_incident(), "amber", 70))


class TestExportFilesAndConfig(unittest.TestCase):
    def test_files_and_checksums_written_locally(self):
        with tempfile.TemporaryDirectory() as tmp:
            exporters = build_ioc_exporters(LocalFilesystem(), Path(tmp), IoCConfig(tlp="green"))
            stix = exporters["stix"].export(_incident())
            misp = exporters["misp"].export(_incident())
            self.assertEqual((stix.path.name, misp.path.name), ("inc-1.stix.json", "inc-1.misp.json"))
            self.assertTrue(Path(f"{stix.path}.sha256").exists())
            self.assertIn(TLP_MARKING_DEFINITIONS["green"], stix.path.read_text())
            self.assertIn("tlp:green", misp.path.read_text())

    def test_defaults_and_validation(self):
        self.assertEqual(IoCConfig().tlp, "amber")
        self.assertEqual(validate_active_defense_config(parse_active_defense_config({"ioc": {"formats": ["stix", "misp"]}})), [])
        errors = validate_active_defense_config(parse_active_defense_config({"ioc": {"formats": ["xml"], "tlp": "orange"}}))
        self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
