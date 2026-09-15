# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""plan_active_defense_omega_serv.md, Phase 4 (decide_incident_closure
jamais appelee auparavant) / Phase 6 ("retention, purge") -
sweep_active_defense.py. Doubles simples, meme discipline que
test_observe_threat.py/test_manage_incidents.py."""
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.application.active_defense.sweep_active_defense import sweep_active_defense
from omega_serv.domain.security.active_defense.config import ActiveDefenseConfig
from omega_serv.domain.security.active_defense.entities import Incident, IncidentEvent, ThreatState

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class _FakeThreatStateRepository:
    def __init__(self):
        self.states: dict[str, ThreatState] = {}

    def get(self, subject_id):
        return self.states.get(subject_id)

    def save(self, state):
        self.states[state.subject_id] = state

    def expire_before(self, instant):
        expired = [sid for sid, s in self.states.items() if s.expires_at < instant]
        for sid in expired:
            del self.states[sid]
        return len(expired)

    def list_all(self):
        return list(self.states.values())


class _FakeIncidentRepository:
    def __init__(self):
        self._incidents: dict[str, Incident] = {}

    def add(self, incident: Incident) -> None:
        self._incidents[incident.incident_id] = incident

    def find_open_for(self, subject_id):
        for incident in self._incidents.values():
            if incident.subject_id == subject_id and incident.status == "open":
                return incident
        return None

    def get(self, incident_id):
        return self._incidents.get(incident_id)

    def create(self, incident_id, subject_id, opened_at):
        raise AssertionError("sweep_active_defense ne cree jamais d'incident")

    def close(self, incident_id, closed_at):
        incident = self._incidents[incident_id]
        self._incidents[incident_id] = Incident(
            incident_id=incident.incident_id, subject_id=incident.subject_id, status="closed",
            opened_at=incident.opened_at, closed_at=closed_at,
            observations=incident.observations, events=incident.events,
        )

    def add_event(self, incident_id, event):
        raise AssertionError("sweep_active_defense n'ajoute jamais d'evenement")

    def add_observation(self, incident_id, observation):
        raise AssertionError("sweep_active_defense n'ajoute jamais d'observation")

    def list_recent(self, filters):
        return [i for i in self._incidents.values() if filters.status is None or i.status == filters.status]


class _FixedClock:
    def __init__(self, now: datetime = _NOW):
        self._now = now

    def now(self) -> datetime:
        return self._now


class TestSweepActiveDefense(unittest.TestCase):
    def test_purges_expired_threat_states(self):
        threat_repo = _FakeThreatStateRepository()
        threat_repo.save(ThreatState(
            subject_id="expired", score=10, level="normal",
            updated_at=_NOW - timedelta(hours=3), expires_at=_NOW - timedelta(hours=1),
        ))
        result = sweep_active_defense(threat_repo, _FakeIncidentRepository(), _FixedClock(), ActiveDefenseConfig())
        self.assertEqual(result.purged_threat_states, 1)

    def test_closes_incident_for_a_source_back_to_normal_and_quiet_long_enough(self):
        threat_repo = _FakeThreatStateRepository()
        threat_repo.save(ThreatState(
            subject_id="s1", score=0, level="normal",
            updated_at=_NOW, expires_at=_NOW + timedelta(hours=1),
        ))
        incident_repo = _FakeIncidentRepository()
        incident_repo.add(Incident(
            incident_id="i1", subject_id="s1", status="open", opened_at=_NOW - timedelta(hours=3),
            events=(IncidentEvent(occurred_at=_NOW - timedelta(hours=3), kind="waf_decision", detail=""),),
        ))
        config = ActiveDefenseConfig(state_ttl_seconds=7200)
        result = sweep_active_defense(threat_repo, incident_repo, _FixedClock(), config)
        self.assertEqual(result.closed_incidents, ("i1",))
        self.assertEqual(incident_repo.get("i1").status, "closed")

    def test_does_not_close_incident_when_still_marked(self):
        threat_repo = _FakeThreatStateRepository()
        threat_repo.save(ThreatState(
            subject_id="s1", score=80, level="hostile",
            updated_at=_NOW, expires_at=_NOW + timedelta(hours=1),
        ))
        incident_repo = _FakeIncidentRepository()
        incident_repo.add(Incident(
            incident_id="i1", subject_id="s1", status="open", opened_at=_NOW - timedelta(hours=3),
            events=(IncidentEvent(occurred_at=_NOW - timedelta(hours=3), kind="waf_decision", detail=""),),
        ))
        result = sweep_active_defense(
            threat_repo, incident_repo, _FixedClock(), ActiveDefenseConfig(state_ttl_seconds=7200),
        )
        self.assertEqual(result.closed_incidents, ())

    def test_does_not_close_incident_when_not_quiet_long_enough(self):
        threat_repo = _FakeThreatStateRepository()
        threat_repo.save(ThreatState(
            subject_id="s1", score=0, level="normal",
            updated_at=_NOW, expires_at=_NOW + timedelta(hours=1),
        ))
        incident_repo = _FakeIncidentRepository()
        incident_repo.add(Incident(
            incident_id="i1", subject_id="s1", status="open", opened_at=_NOW - timedelta(minutes=5),
            events=(IncidentEvent(occurred_at=_NOW - timedelta(minutes=5), kind="waf_decision", detail=""),),
        ))
        result = sweep_active_defense(
            threat_repo, incident_repo, _FixedClock(), ActiveDefenseConfig(state_ttl_seconds=7200),
        )
        self.assertEqual(result.closed_incidents, ())

    def test_missing_threat_state_is_treated_as_normal(self):
        incident_repo = _FakeIncidentRepository()
        incident_repo.add(Incident(
            incident_id="i1", subject_id="s1", status="open", opened_at=_NOW - timedelta(hours=3),
        ))
        result = sweep_active_defense(
            _FakeThreatStateRepository(), incident_repo, _FixedClock(), ActiveDefenseConfig(state_ttl_seconds=7200),
        )
        self.assertEqual(result.closed_incidents, ("i1",))


if __name__ == "__main__":
    unittest.main()
