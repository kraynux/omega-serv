# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""plan_active_defense_omega_serv.md, Phase 4 : "ajouter simulation,
dry-run et explication de la decision dans CLI/TUI" -
PreviewPlaybookDecisionQuery. Doubles simples des trois repositories,
meme discipline que test_observe_threat.py/test_manage_incidents.py/
test_manage_deception.py - le point le plus important a verifier est
qu'AUCUNE ecriture n'a jamais lieu (jamais de .save()/.create() appele)."""
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.application.active_defense.preview_playbook_decision import (
    preview_playbook_decision,
)
from omega_serv.domain.security.active_defense.config import (
    ActiveDefenseConfig,
    DeceptionConfig,
    DeceptionProfileConfig,
    WarModeConfig,
    WarModeThresholds,
)
from omega_serv.domain.security.active_defense.entities import (
    DeceptionAssignment,
    Incident,
    ThreatState,
)

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class _FakeThreatStateRepository:
    def __init__(self):
        self.states: dict[str, ThreatState] = {}
        self.save_called = False

    def get(self, subject_id):
        return self.states.get(subject_id)

    def save(self, state):
        self.save_called = True

    def expire_before(self, instant):
        raise AssertionError("preview_playbook_decision ne doit jamais purger d'etat")

    def list_all(self):
        return list(self.states.values())


class _FakeIncidentRepository:
    def __init__(self):
        self._open_incident: Incident | None = None
        self.create_called = False

    def find_open_for(self, subject_id):
        return self._open_incident

    def get(self, incident_id):
        return None

    def create(self, incident_id, subject_id, opened_at):
        self.create_called = True

    def close(self, incident_id, closed_at):
        raise AssertionError("preview_playbook_decision ne doit jamais fermer d'incident")

    def add_event(self, incident_id, event):
        raise AssertionError("preview_playbook_decision ne doit jamais ecrire d'evenement")

    def add_observation(self, incident_id, observation):
        raise AssertionError("preview_playbook_decision ne doit jamais ecrire d'observation")

    def list_recent(self, filters):
        return []


class _FakeAssignmentRepository:
    def __init__(self):
        self._assignments: dict[str, DeceptionAssignment] = {}
        self.save_called = False

    def get(self, subject_id):
        return self._assignments.get(subject_id)

    def save(self, assignment):
        self.save_called = True

    def release(self, subject_id):
        raise AssertionError("preview_playbook_decision ne doit jamais liberer d'affectation")

    def list_active(self):
        return list(self._assignments.values())


class _FixedClock:
    def __init__(self, now: datetime = _NOW):
        self._now = now

    def now(self) -> datetime:
        return self._now


def _config(**overrides) -> ActiveDefenseConfig:
    defaults = {
        "war_mode": WarModeConfig(
            enabled=True,
            thresholds=WarModeThresholds(suspicious_score=30, hostile_score=60, incident_score=70, contained_score=80),
            actions=("enrich_log", "delay", "rate_limit", "redirect_to_decoy", "create_incident"),
        ),
        "deception": DeceptionConfig(
            enabled=True,
            profiles={"fake_admin": DeceptionProfileConfig(enabled=True, match_attack_classes=("scan",))},
        ),
    }
    defaults.update(overrides)
    return ActiveDefenseConfig(**defaults)


class TestPreviewPlaybookDecision(unittest.TestCase):
    def test_never_writes_to_any_repository(self):
        threat_repo = _FakeThreatStateRepository()
        incident_repo = _FakeIncidentRepository()
        assignment_repo = _FakeAssignmentRepository()
        preview_playbook_decision(
            threat_repo, incident_repo, assignment_repo, _FixedClock(), _config(),
            subject_id="s1", attack_class="scan", score_delta=100,
        )
        self.assertFalse(threat_repo.save_called)
        self.assertFalse(incident_repo.create_called)
        self.assertFalse(assignment_repo.save_called)

    def test_projects_score_and_level_from_a_fresh_subject(self):
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=65,
        )
        self.assertEqual(preview.previous_score, 0)
        self.assertEqual(preview.projected_score, 65)
        self.assertEqual(preview.previous_level, "normal")
        self.assertEqual(preview.projected_level, "hostile")
        self.assertTrue(preview.would_escalate)

    def test_would_assign_deception_when_hostile_and_profile_matches(self):
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=65,
        )
        self.assertTrue(preview.would_assign_deception)
        self.assertEqual(preview.selected_decoy_profile, "fake_admin")

    def test_would_not_assign_deception_when_still_suspicious(self):
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=35,
        )
        self.assertFalse(preview.would_assign_deception)
        self.assertIsNone(preview.selected_decoy_profile)

    def test_would_not_assign_deception_when_already_assigned(self):
        assignment_repo = _FakeAssignmentRepository()
        assignment_repo._assignments["s1"] = DeceptionAssignment(
            subject_id="s1", profile_name="fake_admin", assigned_at=_NOW, expires_at=_NOW + timedelta(hours=1),
        )
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), assignment_repo,
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=65,
        )
        self.assertFalse(preview.would_assign_deception)

    def test_would_create_incident_above_threshold(self):
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=75,
        )
        self.assertTrue(preview.would_create_incident)

    def test_would_not_create_incident_when_action_absent_from_playbook(self):
        config = _config(war_mode=WarModeConfig(enabled=True, actions=("delay",)))
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), config, subject_id="s1", attack_class="scan", score_delta=75,
        )
        self.assertFalse(preview.would_create_incident)

    def test_would_enrich_log_and_delay_when_marked(self):
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=35,
        )
        self.assertTrue(preview.would_enrich_log)
        self.assertTrue(preview.would_delay)
        self.assertEqual(preview.delay_range_ms, (250, 1500))
        self.assertTrue(preview.would_rate_limit)

    def test_would_not_enrich_log_or_delay_when_still_normal(self):
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=0,
        )
        self.assertFalse(preview.would_enrich_log)
        self.assertFalse(preview.would_delay)
        self.assertIsNone(preview.delay_range_ms)
        self.assertFalse(preview.would_rate_limit)

    def test_war_mode_disabled_disables_every_action(self):
        config = _config(war_mode=WarModeConfig(enabled=False))
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), config, subject_id="s1", attack_class="scan", score_delta=100,
        )
        self.assertFalse(preview.would_create_incident)
        self.assertFalse(preview.would_assign_deception)
        self.assertFalse(preview.would_enrich_log)
        self.assertFalse(preview.would_delay)
        self.assertFalse(preview.would_rate_limit)

    def test_explanation_is_never_empty(self):
        preview = preview_playbook_decision(
            _FakeThreatStateRepository(), _FakeIncidentRepository(), _FakeAssignmentRepository(),
            _FixedClock(), _config(), subject_id="s1", attack_class="scan", score_delta=10,
        )
        self.assertTrue(len(preview.explanation) > 0)


if __name__ == "__main__":
    unittest.main()
