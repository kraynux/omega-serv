import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.application.active_defense.queries import (
    get_incident_iocs,
    get_incident_timeline,
    get_threat_state,
    list_incidents,
    list_threat_states,
)
from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentEvent,
    IncidentFilters,
    ThreatObservation,
    ThreatState,
)

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class _FakeIncidentRepository:
    def __init__(self, incidents):
        self._incidents = {i.incident_id: i for i in incidents}

    def find_open_for(self, subject_id):
        return next((i for i in self._incidents.values() if i.subject_id == subject_id and i.status == "open"), None)

    def get(self, incident_id):
        return self._incidents.get(incident_id)

    def create(self, incident_id, subject_id, opened_at):
        raise NotImplementedError

    def close(self, incident_id, closed_at):
        raise NotImplementedError

    def add_event(self, incident_id, event):
        raise NotImplementedError

    def add_observation(self, incident_id, observation):
        raise NotImplementedError

    def list_recent(self, filters: IncidentFilters):
        return list(self._incidents.values())


class _FakeThreatStateRepository:
    def __init__(self, states):
        self._states = {s.subject_id: s for s in states}

    def get(self, subject_id):
        return self._states.get(subject_id)

    def save(self, state):
        self._states[state.subject_id] = state

    def expire_before(self, instant):
        return 0

    def list_all(self):
        return sorted(self._states.values(), key=lambda s: s.score, reverse=True)


def _state(subject_id: str, score: int) -> ThreatState:
    return ThreatState(
        subject_id=subject_id, score=score, level="suspicious", updated_at=_NOW, expires_at=_NOW + timedelta(hours=1),
    )


class TestActiveDefenseQueries(unittest.TestCase):
    def test_list_threat_states_delegates_to_repository(self):
        repository = _FakeThreatStateRepository([_state("low", 10), _state("high", 90)])
        result = list_threat_states(repository)
        self.assertEqual([s.subject_id for s in result], ["high", "low"])

    def test_get_threat_state_found(self):
        repository = _FakeThreatStateRepository([_state("s1", 10)])
        result = get_threat_state(repository, "s1")
        assert result is not None
        self.assertEqual(result.subject_id, "s1")

    def test_get_threat_state_missing_returns_none(self):
        repository = _FakeThreatStateRepository([])
        self.assertIsNone(get_threat_state(repository, "missing"))

    def test_list_threat_states_filters_by_level(self):
        hostile = ThreatState(
            subject_id="h", score=90, level="hostile", updated_at=_NOW, expires_at=_NOW + timedelta(hours=1),
        )
        repository = _FakeThreatStateRepository([_state("low", 10), hostile])
        result = list_threat_states(repository, level="hostile")
        self.assertEqual([s.subject_id for s in result], ["h"])

    def test_list_threat_states_without_level_returns_everything(self):
        repository = _FakeThreatStateRepository([_state("low", 10), _state("high", 90)])
        self.assertEqual(len(list_threat_states(repository, level=None)), 2)


class TestListIncidents(unittest.TestCase):
    def test_delegates_to_repository(self):
        incident = Incident(incident_id="i1", subject_id="s1", status="open", opened_at=_NOW)
        repository = _FakeIncidentRepository([incident])
        self.assertEqual(list_incidents(repository, IncidentFilters()), [incident])


class TestGetIncidentTimeline(unittest.TestCase):
    def test_returns_the_incidents_events(self):
        event = IncidentEvent(occurred_at=_NOW, kind="waf_decision", detail="premiere alerte")
        incident = Incident(incident_id="i1", subject_id="s1", status="open", opened_at=_NOW, events=(event,))
        repository = _FakeIncidentRepository([incident])
        self.assertEqual(get_incident_timeline(repository, "i1"), (event,))

    def test_missing_incident_returns_empty_tuple(self):
        repository = _FakeIncidentRepository([])
        self.assertEqual(get_incident_timeline(repository, "missing"), ())


class TestGetIncidentIoCs(unittest.TestCase):
    def test_extracts_indicators_with_injected_ids(self):
        observation = ThreatObservation(
            subject_id="203.0.113.1:abcd", observed_at=_NOW, kind="waf_decision",
            attack_class="sqli", score_delta=80, detail="WAF block",
        )
        incident = Incident(
            incident_id="i1", subject_id="203.0.113.1:abcd", status="open", opened_at=_NOW,
            observations=(observation,),
        )
        repository = _FakeIncidentRepository([incident])
        counter = iter(("id-1", "id-2"))
        indicators = get_incident_iocs(repository, "i1", id_factory=lambda: next(counter))
        self.assertEqual({i.indicator_id for i in indicators}, {"id-1", "id-2"})

    def test_missing_incident_returns_empty_list(self):
        repository = _FakeIncidentRepository([])
        self.assertEqual(get_incident_iocs(repository, "missing", id_factory=lambda: "x"), [])


if __name__ == "__main__":
    unittest.main()
