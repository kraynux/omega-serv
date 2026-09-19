"""plan_active_defense_omega_serv.md, Phase 2 - vraie I/O reelle
(LocalFilesystem contre un repertoire temporaire), meme discipline que
le reste du projet - jamais de FilesystemPort simule pour un test
d'exporter."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentEvent,
    ThreatObservation,
)
from omega_serv.domain.security.active_defense.policies import hash_payload
from omega_serv.infrastructure.exporters.csv_ioc_exporter import CsvIoCExporter
from omega_serv.infrastructure.exporters.json_ioc_exporter import JsonIoCExporter
from omega_serv.infrastructure.exporters.markdown_incident_report_exporter import (
    MarkdownIncidentReportExporter,
    render_incident_report_markdown,
)
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


def _incident() -> Incident:
    observation = ThreatObservation(
        subject_id="203.0.113.1:abcd1234", observed_at=_NOW, kind="waf_decision",
        attack_class="sqli", score_delta=80, detail="WAF block (regles=SQLI-001)",
    )
    event = IncidentEvent(occurred_at=_NOW, kind="waf_decision", detail="WAF block (regles=SQLI-001)")
    return Incident(
        incident_id="i1", subject_id="203.0.113.1:abcd1234", status="open", opened_at=_NOW,
        observations=(observation,), events=(event,),
    )


class TestJsonIoCExporter(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.export_dir = Path(self._tmp.name) / "exports"
        self.exporter = JsonIoCExporter(LocalFilesystem(), self.export_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_a_real_json_file(self):
        result = self.exporter.export(_incident())
        self.assertEqual(result.export_format, "json")
        self.assertTrue(result.path.exists())
        payload = json.loads(result.path.read_text())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["incident_id"], "i1")
        kinds = {i["kind"] for i in payload["indicators"]}
        self.assertEqual(kinds, {"ip", "user_agent"})

    def test_bytes_written_matches_real_file_size(self):
        result = self.exporter.export(_incident())
        self.assertEqual(result.bytes_written, result.path.stat().st_size)

    def test_writes_a_real_sha256_checksum_sidecar(self):
        """plan_active_defense_omega_serv.md, Phase 6 : "signatures ou
        hachage des exports"."""
        result = self.exporter.export(_incident())
        checksum_path = result.path.with_name(result.path.name + ".sha256")
        self.assertTrue(checksum_path.exists())
        digest, _, filename = checksum_path.read_text().strip().partition("  ")
        self.assertEqual(digest, hash_payload(result.path.read_bytes()))
        self.assertEqual(filename, result.path.name)


class TestCsvIoCExporter(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.export_dir = Path(self._tmp.name) / "exports"
        self.exporter = CsvIoCExporter(LocalFilesystem(), self.export_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_a_real_csv_file_with_shareable_indicators(self):
        result = self.exporter.export(_incident())
        self.assertEqual(result.export_format, "csv")
        content = result.path.read_text()
        self.assertIn("kind,value,confidence,first_seen,last_seen", content)
        self.assertIn("203.0.113.1", content)
        self.assertIn("abcd1234", content)

    def test_writes_a_real_sha256_checksum_sidecar(self):
        result = self.exporter.export(_incident())
        checksum_path = result.path.with_name(result.path.name + ".sha256")
        self.assertTrue(checksum_path.exists())
        digest, _, filename = checksum_path.read_text().strip().partition("  ")
        self.assertEqual(digest, hash_payload(result.path.read_bytes()))
        self.assertEqual(filename, result.path.name)


class TestMarkdownIncidentReportExporter(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.export_dir = Path(self._tmp.name) / "exports"
        self.exporter = MarkdownIncidentReportExporter(LocalFilesystem(), self.export_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_a_real_markdown_file(self):
        result = self.exporter.render(_incident())
        self.assertEqual(result.export_format, "markdown")
        content = result.path.read_text()
        self.assertIn("# Incident i1", content)
        self.assertIn("## Chronologie", content)
        self.assertIn("## Indicateurs de compromission (IoC)", content)
        self.assertIn("waf_decision", content)

    def test_render_function_lists_no_events_explicitly(self):
        empty_incident = Incident(incident_id="i2", subject_id="s2", status="open", opened_at=_NOW)
        content = render_incident_report_markdown(empty_incident)
        self.assertIn("Aucun evenement enregistre", content)
        self.assertIn("Aucun IoC extrait", content)

    def test_writes_a_real_sha256_checksum_sidecar(self):
        result = self.exporter.render(_incident())
        checksum_path = result.path.with_name(result.path.name + ".sha256")
        self.assertTrue(checksum_path.exists())
        digest, _, filename = checksum_path.read_text().strip().partition("  ")
        self.assertEqual(digest, hash_payload(result.path.read_bytes()))
        self.assertEqual(filename, result.path.name)


if __name__ == "__main__":
    unittest.main()
