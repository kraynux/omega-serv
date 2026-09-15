# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""plan_active_defense_omega_serv.md, Phase 2 - double simple du
repository pour tester l'ORCHESTRATION (vraie I/O deja couverte par
test_sqlite_incident_repository.py)."""
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.application.active_defense.manage_incidents import (
    close_incident,
    create_or_update_incident,
)
from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentFilters,
    ThreatObservation,
)

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class _FakeIncidentRepository:
    def __init__(self):
        self._incidents: dict[str, Incident] = {}

    def find_open_for(self, subject_id):
        for incident in self._incidents.values():
            if incident.subject_id == subject_id and incident.status == "open":
                return incident
        return None

    def get(self, incident_id):
        return self._incidents.get(incident_id)

    def create(self, incident_id, subject_id, opened_at):
        self._incidents[incident_id] = Incident(
            incident_id=incident_id, subject_id=subject_id, status="open", opened_at=opened_at,
        )

    def close(self, incident_id, closed_at):
        incident = self._incidents[incident_id]
        self._incidents[incident_id] = Incident(
            incident_id=incident.incident_id, subject_id=incident.subject_id, status="closed",
            opened_at=incident.opened_at, closed_at=closed_at,
            observations=incident.observations, events=incident.events,
        )

    def add_event(self, incident_id, event):
        incident = self._incidents[incident_id]
        self._incidents[incident_id] = Incident(
            incident_id=incident.incident_id, subject_id=incident.subject_id, status=incident.status,
            opened_at=incident.opened_at, closed_at=incident.closed_at,
            observations=incident.observations, events=(*incident.events, event),
        )

    def add_observation(self, incident_id, observation):
        incident = self._incidents[incident_id]
        self._incidents[incident_id] = Incident(
            incident_id=incident.incident_id, subject_id=incident.subject_id, status=incident.status,
            opened_at=incident.opened_at, closed_at=incident.closed_at,
            observations=(*incident.observations, observation), events=incident.events,
        )

    def list_recent(self, filters: IncidentFilters):
        return list(self._incidents.values())


class _FixedClock:
    def __init__(self, now: datetime = _NOW):
        self._now = now

    def now(self) -> datetime:
        return self._now


def _observation(**overrides) -> ThreatObservation:
    defaults = {
        "subject_id": "s1", "observed_at": _NOW, "kind": "waf_decision",
        "attack_class": "sqli", "score_delta": 80, "detail": "WAF block",
    }
    defaults.update(overrides)
    return ThreatObservation(**defaults)


class TestCreateOrUpdateIncident(unittest.TestCase):
    def test_below_threshold_creates_nothing(self):
        repository = _FakeIncidentRepository()
        incident, opened = create_or_update_incident(
            repository, _FixedClock(), subject_id="s1", observation=_observation(),
            score=50, incident_score_threshold=70,
        )
        self.assertIsNone(incident)
        self.assertIsNone(opened)
        self.assertIsNone(repository.find_open_for("s1"))

    def test_above_threshold_opens_a_new_incident(self):
        repository = _FakeIncidentRepository()
        incident, opened = create_or_update_incident(
            repository, _FixedClock(), subject_id="s1", observation=_observation(),
            score=80, incident_score_threshold=70,
        )
        assert incident is not None
        assert opened is not None
        self.assertEqual(incident.subject_id, "s1")
        self.assertEqual(incident.status, "open")
        self.assertEqual(len(incident.observations), 1)
        self.assertEqual(len(incident.events), 1)
        self.assertEqual(opened.subject_id, "s1")

    def test_second_observation_merges_into_the_same_open_incident(self):
        repository = _FakeIncidentRepository()
        first, _ = create_or_update_incident(
            repository, _FixedClock(), subject_id="s1", observation=_observation(),
            score=80, incident_score_threshold=70,
        )
        assert first is not None
        second, opened = create_or_update_incident(
            repository, _FixedClock(now=_NOW + timedelta(minutes=1)), subject_id="s1",
            observation=_observation(score_delta=25, kind="reputation_escalation"),
            score=105, incident_score_threshold=70,
        )
        assert second is not None
        self.assertIsNone(opened)  # pas un second IncidentOpened
        self.assertEqual(second.incident_id, first.incident_id)
        self.assertEqual(len(second.observations), 2)


class TestCloseIncident(unittest.TestCase):
    def test_closes_an_open_incident(self):
        repository = _FakeIncidentRepository()
        repository.create("i1", "s1", _NOW)
        closed = close_incident(repository, _FixedClock(now=_NOW + timedelta(hours=1)), "i1")
        assert closed is not None
        self.assertEqual(closed.status, "closed")
        self.assertEqual(closed.closed_at, _NOW + timedelta(hours=1))

    def test_missing_incident_returns_none(self):
        repository = _FakeIncidentRepository()
        self.assertIsNone(close_incident(repository, _FixedClock(), "does-not-exist"))

    def test_already_closed_incident_is_a_no_op(self):
        repository = _FakeIncidentRepository()
        repository.create("i1", "s1", _NOW)
        close_incident(repository, _FixedClock(now=_NOW + timedelta(hours=1)), "i1")
        self.assertIsNone(close_incident(repository, _FixedClock(now=_NOW + timedelta(hours=2)), "i1"))


if __name__ == "__main__":
    unittest.main()
