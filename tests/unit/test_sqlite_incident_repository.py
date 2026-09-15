# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""plan_active_defense_omega_serv.md, Phase 2 - vraie I/O reelle contre
un fichier sqlite temporaire, meme discipline que
test_sqlite_threat_state_repository.py."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import (
    IncidentEvent,
    IncidentFilters,
    ThreatObservation,
)
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_incident_repository import (
    SqliteIncidentRepository,
)

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class TestSqliteIncidentRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.database_path = Path(self._tmp.name) / "active-defense.sqlite3"
        self.connection = open_active_defense_connection(self.database_path)
        self.repository = SqliteIncidentRepository(self.connection)

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def _observation(self, **overrides) -> ThreatObservation:
        defaults = {
            "subject_id": "203.0.113.1:abcd", "observed_at": _NOW, "kind": "waf_decision",
            "attack_class": "sqli", "score_delta": 10, "detail": "WAF block (regles=R1)",
        }
        defaults.update(overrides)
        return ThreatObservation(**defaults)

    def test_get_missing_incident_returns_none(self):
        self.assertIsNone(self.repository.get("does-not-exist"))

    def test_find_open_for_missing_subject_returns_none(self):
        self.assertIsNone(self.repository.find_open_for("203.0.113.1:abcd"))

    def test_create_then_get_round_trips(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        incident = self.repository.get("i1")
        assert incident is not None
        self.assertEqual(incident.subject_id, "203.0.113.1:abcd")
        self.assertEqual(incident.status, "open")
        self.assertIsNone(incident.closed_at)
        self.assertEqual(incident.observations, ())
        self.assertEqual(incident.events, ())

    def test_find_open_for_finds_the_open_incident(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        incident = self.repository.find_open_for("203.0.113.1:abcd")
        assert incident is not None
        self.assertEqual(incident.incident_id, "i1")

    def test_closed_incident_is_not_found_by_find_open_for(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        self.repository.close("i1", _NOW + timedelta(hours=1))
        self.assertIsNone(self.repository.find_open_for("203.0.113.1:abcd"))
        closed = self.repository.get("i1")
        assert closed is not None
        self.assertEqual(closed.status, "closed")
        self.assertEqual(closed.closed_at, _NOW + timedelta(hours=1))

    def test_add_observation_appends_without_duplicating(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        self.repository.add_observation("i1", self._observation())
        self.repository.add_observation("i1", self._observation(score_delta=25, kind="reputation_escalation"))
        incident = self.repository.get("i1")
        assert incident is not None
        self.assertEqual(len(incident.observations), 2)
        self.assertEqual(incident.observations[0].score_delta, 10)
        self.assertEqual(incident.observations[1].kind, "reputation_escalation")

    def test_add_event_appends_a_timeline_entry(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        self.repository.add_event("i1", IncidentEvent(occurred_at=_NOW, kind="waf_decision", detail="premiere alerte"))
        incident = self.repository.get("i1")
        assert incident is not None
        self.assertEqual(len(incident.events), 1)
        self.assertEqual(incident.events[0].detail, "premiere alerte")

    def test_list_recent_filters_by_status(self):
        self.repository.create("open-one", "s1", _NOW)
        self.repository.create("closed-one", "s2", _NOW)
        self.repository.close("closed-one", _NOW + timedelta(hours=1))
        open_only = self.repository.list_recent(IncidentFilters(status="open"))
        self.assertEqual([i.incident_id for i in open_only], ["open-one"])

    def test_list_recent_filters_by_since(self):
        self.repository.create("old", "s1", _NOW - timedelta(days=2))
        self.repository.create("recent", "s2", _NOW)
        recent_only = self.repository.list_recent(IncidentFilters(since=_NOW - timedelta(hours=1)))
        self.assertEqual([i.incident_id for i in recent_only], ["recent"])

    def test_list_recent_orders_by_opened_at_descending(self):
        self.repository.create("first", "s1", _NOW)
        self.repository.create("second", "s2", _NOW + timedelta(minutes=5))
        result = self.repository.list_recent(IncidentFilters())
        self.assertEqual([i.incident_id for i in result], ["second", "first"])


if __name__ == "__main__":
    unittest.main()
