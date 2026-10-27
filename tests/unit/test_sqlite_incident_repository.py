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


class TestIncidentHistoryPruning(unittest.TestCase):
    """Decision utilisateur 2026-10-26 : un attaquant persistant ajoutait 2 lignes par requete a
    un incident ouvert, sans limite. On garde le debut et la fin, le milieu est compte."""

    setUp = TestSqliteIncidentRepository.setUp
    tearDown = TestSqliteIncidentRepository.tearDown
    _observation = TestSqliteIncidentRepository._observation

    def test_keeps_first_and_last_and_counts_the_middle(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        for index in range(10):
            at = _NOW + timedelta(seconds=index)
            self.repository.add_observation("i1", self._observation(observed_at=at, detail=f"o{index}"))
            self.repository.add_event("i1", IncidentEvent(occurred_at=at, kind="waf_decision", detail=f"e{index}"))
        self.assertEqual(self.repository.prune_history(keep_first=2, keep_last=3), 10)
        incident = self.repository.get("i1")
        self.assertEqual([o.detail for o in incident.observations], ["o0", "o1", "o7", "o8", "o9"])
        self.assertEqual([e.detail for e in incident.events], ["e0", "e1", "e7", "e8", "e9"])
        self.assertEqual((incident.omitted_observations, incident.omitted_events), (5, 5))
        # un second elagage ajoute au compteur, jamais ne le remet a zero
        for index in range(10, 13):
            self.repository.add_event("i1", IncidentEvent(occurred_at=_NOW + timedelta(seconds=index), kind="k", detail=f"e{index}"))
        self.repository.prune_history(keep_first=2, keep_last=3)
        self.assertEqual(self.repository.get("i1").omitted_events, 8)

    def test_small_history_untouched(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        self.repository.add_event("i1", IncidentEvent(occurred_at=_NOW, kind="k", detail="seul"))
        self.assertEqual(self.repository.prune_history(keep_first=2, keep_last=3), 0)
        self.assertEqual(self.repository.get("i1").omitted_events, 0)

    def test_find_open_id_for_does_not_need_the_history(self):
        self.repository.create("i1", "203.0.113.1:abcd", _NOW)
        self.assertEqual(self.repository.find_open_id_for("203.0.113.1:abcd"), "i1")
        self.repository.close("i1", _NOW)
        self.assertIsNone(self.repository.find_open_id_for("203.0.113.1:abcd"))

if __name__ == "__main__":
    unittest.main()
