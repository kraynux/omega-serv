# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""plan_active_defense_omega_serv.md, Phase 3 - double simple du
repository pour tester l'ORCHESTRATION (vraie I/O deja couverte par
test_sqlite_deception_assignment_repository.py), meme discipline que
test_manage_incidents.py."""
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.application.active_defense.manage_deception import (
    assign_deception,
    release_deception,
    resolve_routing_decision,
)
from omega_serv.domain.security.active_defense.config import DeceptionConfig, DeceptionProfileConfig
from omega_serv.domain.security.active_defense.entities import DeceptionAssignment

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class _FakeAssignmentRepository:
    def __init__(self):
        self._assignments: dict[str, DeceptionAssignment] = {}

    def get(self, subject_id):
        return self._assignments.get(subject_id)

    def save(self, assignment):
        self._assignments[assignment.subject_id] = assignment

    def release(self, subject_id):
        self._assignments.pop(subject_id, None)

    def list_active(self):
        return list(self._assignments.values())


class _FixedClock:
    def __init__(self, now: datetime = _NOW):
        self._now = now

    def now(self) -> datetime:
        return self._now


def _config(**overrides) -> DeceptionConfig:
    defaults = {
        "enabled": True,
        "fallback": "pass_through",
        "assignments_ttl_seconds": 7200,
        "profiles": {
            "fake_admin": DeceptionProfileConfig(enabled=True, match_attack_classes=("credential_stuffing", "scan")),
        },
    }
    defaults.update(overrides)
    return DeceptionConfig(**defaults)


class TestAssignDeception(unittest.TestCase):
    def test_disabled_deception_assigns_nothing(self):
        repository = _FakeAssignmentRepository()
        result = assign_deception(
            repository, _FixedClock(), _config(enabled=False), subject_id="s1", attack_class="scan",
        )
        self.assertIsNone(result)
        self.assertIsNone(repository.get("s1"))

    def test_no_matching_profile_assigns_nothing(self):
        repository = _FakeAssignmentRepository()
        result = assign_deception(
            repository, _FixedClock(), _config(), subject_id="s1", attack_class="sqli",
        )
        self.assertIsNone(result)

    def test_matching_attack_class_creates_an_assignment_with_ttl(self):
        repository = _FakeAssignmentRepository()
        result = assign_deception(
            repository, _FixedClock(), _config(), subject_id="s1", attack_class="scan",
        )
        assert result is not None
        self.assertEqual(result.subject_id, "s1")
        self.assertEqual(result.profile_name, "fake_admin")
        self.assertEqual(result.assigned_at, _NOW)
        self.assertEqual(result.expires_at, _NOW + timedelta(seconds=7200))
        self.assertEqual(repository.get("s1"), result)

    def test_existing_assignment_is_never_replaced(self):
        repository = _FakeAssignmentRepository()
        first = assign_deception(
            repository, _FixedClock(), _config(), subject_id="s1", attack_class="scan",
        )
        second = assign_deception(
            repository, _FixedClock(now=_NOW + timedelta(minutes=1)), _config(), subject_id="s1",
            attack_class="credential_stuffing",
        )
        self.assertIsNone(second)
        self.assertEqual(repository.get("s1"), first)


class TestReleaseDeception(unittest.TestCase):
    def test_releases_an_existing_assignment(self):
        repository = _FakeAssignmentRepository()
        assign_deception(repository, _FixedClock(), _config(), subject_id="s1", attack_class="scan")
        release_deception(repository, "s1")
        self.assertIsNone(repository.get("s1"))

    def test_releasing_a_missing_assignment_is_a_no_op(self):
        repository = _FakeAssignmentRepository()
        release_deception(repository, "does-not-exist")  # ne leve jamais


class TestResolveRoutingDecision(unittest.TestCase):
    def test_no_assignment_is_production(self):
        repository = _FakeAssignmentRepository()
        decision = resolve_routing_decision(repository, _FixedClock(), _config(), "s1")
        self.assertEqual(decision.kind, "production")

    def test_active_assignment_is_decoy_fixture(self):
        repository = _FakeAssignmentRepository()
        assign_deception(repository, _FixedClock(), _config(), subject_id="s1", attack_class="scan")
        decision = resolve_routing_decision(repository, _FixedClock(), _config(), "s1")
        self.assertEqual(decision.kind, "decoy_fixture")
        self.assertEqual(decision.deception_profile_name, "fake_admin")

    def test_expired_assignment_is_production(self):
        repository = _FakeAssignmentRepository()
        assign_deception(
            repository, _FixedClock(), _config(assignments_ttl_seconds=60), subject_id="s1", attack_class="scan",
        )
        decision = resolve_routing_decision(
            repository, _FixedClock(now=_NOW + timedelta(seconds=61)), _config(), "s1",
        )
        self.assertEqual(decision.kind, "production")

    def test_proxy_isolation_level_resolves_to_decoy_proxy(self):
        """plan_active_defense_omega_serv.md, Phase 5 ("Niveau 2") - le
        profil affecte porte l'isolation_level, jamais l'affectation
        elle-meme."""
        repository = _FakeAssignmentRepository()
        config = _config(profiles={
            "fake_admin": DeceptionProfileConfig(
                enabled=True, match_attack_classes=("scan",),
                isolation_level="proxy", reverse_proxy_zone_name="decoy-zone",
            ),
        })
        assign_deception(repository, _FixedClock(), config, subject_id="s1", attack_class="scan")
        decision = resolve_routing_decision(repository, _FixedClock(), config, "s1")
        self.assertEqual(decision.kind, "decoy_proxy")
        self.assertEqual(decision.deception_profile_name, "fake_admin")
        self.assertEqual(decision.reverse_proxy_zone_name, "decoy-zone")

    def test_profile_removed_since_assignment_falls_back_to_fixture(self):
        repository = _FakeAssignmentRepository()
        assign_deception(repository, _FixedClock(), _config(), subject_id="s1", attack_class="scan")
        decision = resolve_routing_decision(repository, _FixedClock(), _config(profiles={}), "s1")
        self.assertEqual(decision.kind, "decoy_fixture")


if __name__ == "__main__":
    unittest.main()
