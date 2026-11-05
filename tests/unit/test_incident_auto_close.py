"""Fermeture automatique des incidents (decision utilisateur 2026-11-01) : un incident dont la menace est
effacee quitte la liste tout seul - entretien du serveur (fil d'ecriture), export automatique commun."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.active_defense.auto_export import auto_export_closed_incidents
from omega_serv.application.server.start_server import incident_maintenance
from omega_serv.domain.security.active_defense.config import parse_active_defense_config
from omega_serv.domain.security.active_defense.entities import (
    IncidentEvent,
    IncidentFilters,
    ThreatState,
)
from omega_serv.infrastructure.persistence.active_defense_write_behind import (
    SqliteActiveDefenseWriter,
)
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_deception_assignment_repository import (
    SqliteDeceptionAssignmentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_incident_repository import (
    SqliteIncidentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
    SqliteThreatStateRepository,
)
from omega_serv.ports.active_defense_writer_port import ActiveDefenseRepositories

NOW = datetime(2026, 11, 1, 20, tzinfo=timezone.utc)


class _Clock:
    def now(self):
        return NOW


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.database = self.root / "var" / "lib" / "active-defense.sqlite3"
        self.connection = open_active_defense_connection(self.database)
        self.repositories = ActiveDefenseRepositories(
            threat_states=SqliteThreatStateRepository(self.connection),
            incidents=SqliteIncidentRepository(self.connection),
            deception_assignments=SqliteDeceptionAssignmentRepository(self.connection),
        )

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def _incident(self, incident_id, subject, last_event_hours_ago):
        at = NOW - timedelta(hours=last_event_hours_ago)
        self.repositories.incidents.create(incident_id, subject, at)
        self.repositories.incidents.add_event(incident_id, IncidentEvent(occurred_at=at, kind="waf_decision", detail="x"))

    def _open_ids(self):
        return {i.incident_id for i in self.repositories.incidents.list_recent(IncidentFilters(status="open"))}


class TestServerMaintenance(_Base):
    def test_incident_whose_threat_is_erased_is_closed(self):
        self._incident("efface", "203.0.113.1:a", last_event_hours_ago=5)   # plus d'etat de menace, calme
        self._incident("recent", "203.0.113.2:b", last_event_hours_ago=0.5)  # calme depuis trop peu
        self._incident("hostile", "203.0.113.3:c", last_event_hours_ago=5)
        self.repositories.threat_states.save(ThreatState(
            subject_id="203.0.113.3:c", score=90, level="hostile", updated_at=NOW, expires_at=NOW + timedelta(hours=2)))
        incident_maintenance(parse_active_defense_config({}), self.root, _Clock())(self.repositories)
        self.assertEqual(self._open_ids(), {"recent", "hostile"})

    def test_auto_export_on_close_writes_the_configured_formats(self):
        self._incident("efface", "203.0.113.1:a", last_event_hours_ago=5)
        config = parse_active_defense_config({"ioc": {"auto_export_on_close": True, "formats": ["json", "markdown"]}})
        incident_maintenance(config, self.root, _Clock())(self.repositories)
        export_dir = self.root / config.storage.export_dir
        self.assertTrue((export_dir / "efface.json").exists())
        self.assertTrue((export_dir / "efface.md").exists())

    def test_writer_runs_the_maintenance_and_never_lets_it_cancel_the_purge(self):
        calls, reports = [], []
        writer = SqliteActiveDefenseWriter(self.database, _Clock(), after_purge=calls.append)
        writer._purge_job(self.repositories)
        self.assertEqual(calls, [self.repositories])

        def broken(_repositories):
            raise RuntimeError("panne")
        writer = SqliteActiveDefenseWriter(self.database, _Clock(), after_purge=broken)
        writer._report = reports.append
        writer._purge_job(self.repositories)  # jamais d'exception
        self.assertTrue(reports and "panne" in reports[0])


class TestAutoExport(_Base):
    def test_disabled_option_exports_nothing(self):
        self._incident("i", "s:a", 5)
        disabled = parse_active_defense_config({"ioc": {"auto_export_on_close": False}})  # active par defaut
        written = auto_export_closed_incidents(["i"], self.repositories.incidents, disabled,
                                               lambda *_a: "fichier", lambda _i: "rapport")
        self.assertEqual(written, 0)

    def test_one_failure_never_stops_the_other_exports(self):
        self._incident("i", "s:a", 5)
        config = parse_active_defense_config({"ioc": {"auto_export_on_close": True, "formats": ["json", "csv", "markdown"]}})
        errors = []

        def export_ioc(_incident, export_format):
            if export_format == "json":
                raise OSError("disque plein")
            return "fichier"

        written = auto_export_closed_incidents(["i", "inconnu"], self.repositories.incidents, config, export_ioc,
                                               lambda _i: "rapport", errors.append)
        self.assertEqual(written, 2)  # csv + markdown
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
