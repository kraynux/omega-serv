# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""plan_active_defense_omega_serv.md, Phase 1/2 - double simple de
ThreatStateRepositoryPort pour tester l'ORCHESTRATION (jamais de vraie
I/O ici, deja couverte par test_sqlite_threat_state_repository.py -
meme separation que TestCreateInstanceOrchestration/TestCreateInstanceRealVenv)."""
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.application.active_defense.observe_threat import (
    observe_threat,
    purge_expired_threat_states,
)
from omega_serv.domain.security.active_defense.config import (
    ActiveDefenseConfig,
    WarModeConfig,
    WarModeThresholds,
)
from omega_serv.domain.security.active_defense.entities import ThreatState
from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding
from omega_serv.domain.security.waf.reputation import ReputationDecision

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class _FakeThreatStateRepository:
    def __init__(self):
        self.states: dict[str, ThreatState] = {}
        self.save_calls: list[ThreatState] = []

    def get(self, subject_id):
        return self.states.get(subject_id)

    def save(self, state):
        self.states[state.subject_id] = state
        self.save_calls.append(state)

    def expire_before(self, instant):
        expired = [sid for sid, s in self.states.items() if s.expires_at < instant]
        for sid in expired:
            del self.states[sid]
        return len(expired)

    def list_all(self):
        return sorted(self.states.values(), key=lambda s: s.score, reverse=True)


class _FixedClock:
    def __init__(self, now: datetime = _NOW):
        self._now = now

    def now(self) -> datetime:
        return self._now


def _config(**threshold_overrides) -> ActiveDefenseConfig:
    thresholds = WarModeThresholds(**threshold_overrides) if threshold_overrides else WarModeThresholds()
    return ActiveDefenseConfig(state_ttl_seconds=7200, war_mode=WarModeConfig(thresholds=thresholds))


def _blocked_waf_decision() -> WafDecision:
    finding = WafFinding(rule_id="R1", pack="p", description="", severity=Severity.HIGH, weight=10, scope="path")
    return WafDecision(action="block", status_code=403, score=10, findings=(finding,))


class TestObserveThreat(unittest.TestCase):
    def test_first_observation_creates_a_fresh_state(self):
        repository = _FakeThreatStateRepository()
        state, observation, escalation = observe_threat(
            repository, _FixedClock(), _config(), subject_id="s1", waf_decision=_blocked_waf_decision(),
        )
        self.assertEqual(state.score, 10)
        self.assertEqual(state.level, "normal")
        self.assertIsNone(escalation)
        self.assertEqual(repository.get("s1"), state)
        assert observation is not None
        self.assertEqual(observation.subject_id, "s1")
        self.assertEqual(observation.kind, "waf_decision")
        self.assertEqual(observation.score_delta, 10)

    def test_no_signal_at_all_returns_no_observation(self):
        repository = _FakeThreatStateRepository()
        state, observation, escalation = observe_threat(repository, _FixedClock(), _config(), subject_id="s1")
        self.assertEqual(state.score, 0)
        self.assertIsNone(observation)
        self.assertIsNone(escalation)

    def test_allow_waf_decision_produces_no_observation(self):
        repository = _FakeThreatStateRepository()
        allow_decision = WafDecision(action="allow", status_code=None, score=0, findings=())
        _, observation, _ = observe_threat(
            repository, _FixedClock(), _config(), subject_id="s1", waf_decision=allow_decision,
        )
        self.assertIsNone(observation)

    def test_expires_at_reflects_state_ttl(self):
        repository = _FakeThreatStateRepository()
        config = ActiveDefenseConfig(state_ttl_seconds=999)
        state, _, _ = observe_threat(repository, _FixedClock(), config, subject_id="s1")
        self.assertEqual(state.expires_at, _NOW + timedelta(seconds=999))

    def test_escalation_event_emitted_only_when_level_actually_increases(self):
        repository = _FakeThreatStateRepository()
        config = _config(suspicious_score=5, hostile_score=60, incident_score=70, contained_score=80)
        _, _, first_escalation = observe_threat(
            repository, _FixedClock(), config, subject_id="s1", waf_decision=_blocked_waf_decision(),
        )
        self.assertIsNotNone(first_escalation)
        assert first_escalation is not None
        self.assertEqual(first_escalation.previous_level, "normal")
        self.assertEqual(first_escalation.new_level, "suspicious")

    def test_no_escalation_event_when_level_stays_the_same(self):
        repository = _FakeThreatStateRepository()
        repository.save(ThreatState(
            subject_id="s1", score=50, level="suspicious", updated_at=_NOW, expires_at=_NOW + timedelta(hours=2),
        ))
        _, _, escalation = observe_threat(repository, _FixedClock(now=_NOW), _config(), subject_id="s1")
        self.assertIsNone(escalation)

    def test_reputation_escalation_contributes_to_the_score(self):
        repository = _FakeThreatStateRepository()
        state, observation, _ = observe_threat(
            repository, _FixedClock(), _config(), subject_id="s1",
            reputation_decision=ReputationDecision(True, "seuil atteint"),
        )
        self.assertEqual(state.score, 25)
        assert observation is not None
        self.assertEqual(observation.kind, "reputation_escalation")

    def test_known_ban_contributes_to_the_score_and_enables_contained(self):
        repository = _FakeThreatStateRepository()
        config = _config(suspicious_score=10, hostile_score=20, incident_score=30, contained_score=25)
        state, _, _ = observe_threat(
            repository, _FixedClock(), config, subject_id="s1",
            waf_decision=_blocked_waf_decision(), known_ban=True,
        )
        self.assertEqual(state.level, "contained")

    def test_preserves_active_actions_across_observations(self):
        repository = _FakeThreatStateRepository()
        repository.save(ThreatState(
            subject_id="s1", score=10, level="normal", updated_at=_NOW, expires_at=_NOW + timedelta(hours=2),
            active_actions=("enrich_log",),
        ))
        state, _, _ = observe_threat(
            repository, _FixedClock(), _config(), subject_id="s1", waf_decision=_blocked_waf_decision(),
        )
        self.assertEqual(state.active_actions, ("enrich_log",))


class TestPurgeExpiredThreatStates(unittest.TestCase):
    def test_returns_the_number_of_removed_entries(self):
        repository = _FakeThreatStateRepository()
        repository.save(ThreatState(
            subject_id="expired", score=10, level="normal",
            updated_at=_NOW - timedelta(hours=3), expires_at=_NOW - timedelta(hours=1),
        ))
        repository.save(ThreatState(
            subject_id="still-valid", score=10, level="normal",
            updated_at=_NOW, expires_at=_NOW + timedelta(hours=1),
        ))
        removed = purge_expired_threat_states(repository, _FixedClock())
        self.assertEqual(removed, 1)
        self.assertIsNone(repository.get("expired"))


if __name__ == "__main__":
    unittest.main()
