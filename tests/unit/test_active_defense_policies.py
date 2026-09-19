"""plan_active_defense_omega_serv.md, Phase 0 - critere de sortie :
toutes les decisions metier sont testees sans serveur HTTP, SQLite,
Textual ni filesystem."""
import unittest
from datetime import datetime, timedelta, timezone
from typing import ClassVar

from omega_serv.domain.security.active_defense.config import WarModeConfig
from omega_serv.domain.security.active_defense.entities import (
    DeceptionAssignment,
    DeceptionProfile,
    DefensePlaybook,
    Incident,
    ThreatObservation,
)
from omega_serv.domain.security.active_defense.policies import (
    apply_observation,
    attack_class_for_waf_decision,
    build_observation_from_waf_decision,
    build_playbook,
    compute_slowdown_delay_ms,
    decay_score,
    decide_incident_closure,
    decide_incident_transition,
    extract_indicator_candidates,
    extract_indicators,
    hash_payload,
    is_assignment_active,
    is_source_marked,
    qualify_threat_level,
    redact_fields,
    score_delta_for_reputation_escalation,
    score_delta_for_waf_decision,
    select_decoy_profile,
    validate_playbook_action,
)
from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding
from omega_serv.domain.security.waf.reputation import ReputationDecision

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


def _finding() -> WafFinding:
    return WafFinding(rule_id="R1", pack="p", description="", severity=Severity.HIGH, weight=10, scope="path")


class TestScoreDeltaFromExistingWafDecisions(unittest.TestCase):
    """Correction majeure du plan : Active Defense consomme les
    decisions WAF deja calculees, il ne recalcule jamais un score
    independant."""

    def test_blocked_waf_decision_contributes_a_delta(self):
        decision = WafDecision(action="block", status_code=403, score=10, findings=(_finding(),))
        self.assertEqual(score_delta_for_waf_decision(decision), 10)

    def test_log_only_waf_decision_with_findings_still_contributes(self):
        decision = WafDecision(action="log", status_code=None, score=10, findings=(_finding(),))
        self.assertEqual(score_delta_for_waf_decision(decision), 10)

    def test_allow_waf_decision_contributes_nothing(self):
        decision = WafDecision(action="allow", status_code=None, score=0, findings=())
        self.assertEqual(score_delta_for_waf_decision(decision), 0)

    def test_reputation_escalation_contributes_a_delta(self):
        self.assertEqual(score_delta_for_reputation_escalation(ReputationDecision(True, "seuil atteint")), 25)

    def test_no_reputation_escalation_contributes_nothing(self):
        self.assertEqual(score_delta_for_reputation_escalation(ReputationDecision(False, "sous le seuil")), 0)


class TestQualifyThreatLevel(unittest.TestCase):
    _KWARGS: ClassVar[dict[str, int]] = {"suspicious_score": 30, "hostile_score": 60, "contained_score": 80}

    def test_below_suspicious_is_normal(self):
        self.assertEqual(qualify_threat_level(0, known_ban=False, **self._KWARGS), "normal")
        self.assertEqual(qualify_threat_level(29, known_ban=False, **self._KWARGS), "normal")

    def test_suspicious_threshold(self):
        self.assertEqual(qualify_threat_level(30, known_ban=False, **self._KWARGS), "suspicious")
        self.assertEqual(qualify_threat_level(59, known_ban=False, **self._KWARGS), "suspicious")

    def test_hostile_threshold(self):
        self.assertEqual(qualify_threat_level(60, known_ban=False, **self._KWARGS), "hostile")
        self.assertEqual(qualify_threat_level(79, known_ban=False, **self._KWARGS), "hostile")

    def test_contained_requires_both_score_and_known_ban(self):
        self.assertEqual(qualify_threat_level(80, known_ban=True, **self._KWARGS), "contained")
        self.assertEqual(qualify_threat_level(100, known_ban=False, **self._KWARGS), "hostile")


class TestDecayScore(unittest.TestCase):
    def test_no_decay_before_first_interval(self):
        self.assertEqual(decay_score(50, elapsed_seconds=100, decay_amount=5, decay_interval_seconds=900), 50)

    def test_one_interval_decays_once(self):
        self.assertEqual(decay_score(50, elapsed_seconds=900, decay_amount=5, decay_interval_seconds=900), 45)

    def test_multiple_intervals_decay_proportionally(self):
        self.assertEqual(decay_score(50, elapsed_seconds=2700, decay_amount=5, decay_interval_seconds=900), 35)

    def test_never_decays_below_zero(self):
        self.assertEqual(decay_score(10, elapsed_seconds=9000, decay_amount=5, decay_interval_seconds=900), 0)

    def test_disabled_decay_interval_is_a_no_op(self):
        self.assertEqual(decay_score(50, elapsed_seconds=99999, decay_amount=5, decay_interval_seconds=0), 50)


class TestApplyObservation(unittest.TestCase):
    _KWARGS: ClassVar[dict[str, int]] = {"suspicious_score": 30, "hostile_score": 60, "contained_score": 80}

    def test_decays_then_adds_the_new_delta(self):
        score, level = apply_observation(
            current_score=50, last_updated_at=_NOW - timedelta(seconds=900), now=_NOW,
            score_delta=10, known_ban=False, **self._KWARGS,
        )
        self.assertEqual(score, 55)
        self.assertEqual(level, "suspicious")

    def test_fresh_state_with_no_elapsed_time_just_adds(self):
        score, level = apply_observation(
            current_score=0, last_updated_at=_NOW, now=_NOW, score_delta=35, known_ban=False, **self._KWARGS,
        )
        self.assertEqual(score, 35)
        self.assertEqual(level, "suspicious")


class TestSelectDecoyProfile(unittest.TestCase):
    def test_returns_first_enabled_matching_profile(self):
        profiles = (
            DeceptionProfile(name="fake_cms", enabled=True, match_attack_classes=("sqli",)),
            DeceptionProfile(name="fake_admin", enabled=True, match_attack_classes=("scan", "credential_stuffing")),
        )
        selected = select_decoy_profile("scan", profiles)
        assert selected is not None
        self.assertEqual(selected.name, "fake_admin")

    def test_skips_disabled_profiles(self):
        profiles = (
            DeceptionProfile(name="fake_admin", enabled=False, match_attack_classes=("scan",)),
        )
        self.assertIsNone(select_decoy_profile("scan", profiles))

    def test_no_match_returns_none(self):
        profiles = (DeceptionProfile(name="fake_admin", enabled=True, match_attack_classes=("scan",)),)
        self.assertIsNone(select_decoy_profile("sqli", profiles))

    def test_deterministic_order_first_match_wins(self):
        profiles = (
            DeceptionProfile(name="first", enabled=True, match_attack_classes=("scan",)),
            DeceptionProfile(name="second", enabled=True, match_attack_classes=("scan",)),
        )
        selected = select_decoy_profile("scan", profiles)
        assert selected is not None
        self.assertEqual(selected.name, "first")


class TestIsAssignmentActive(unittest.TestCase):
    def _assignment(self, **overrides) -> DeceptionAssignment:
        defaults = {
            "subject_id": "s1", "profile_name": "fake_admin",
            "assigned_at": _NOW, "expires_at": _NOW + timedelta(hours=2),
        }
        defaults.update(overrides)
        return DeceptionAssignment(**defaults)

    def test_before_expiry_is_active(self):
        assignment = self._assignment()
        self.assertTrue(is_assignment_active(assignment, _NOW + timedelta(hours=1)))

    def test_after_expiry_is_not_active(self):
        assignment = self._assignment()
        self.assertFalse(is_assignment_active(assignment, _NOW + timedelta(hours=3)))

    def test_exactly_at_expiry_is_not_active(self):
        assignment = self._assignment()
        self.assertFalse(is_assignment_active(assignment, assignment.expires_at))


class TestDecideIncidentTransition(unittest.TestCase):
    """Base sur le score brut, jamais ThreatLevel (correction Phase 2 -
    voir le docstring de decide_incident_transition)."""

    def test_below_threshold_is_no_change(self):
        self.assertEqual(decide_incident_transition(None, 50, incident_score_threshold=70), "no_change")

    def test_above_threshold_without_existing_incident_opens_new(self):
        self.assertEqual(decide_incident_transition(None, 70, incident_score_threshold=70), "open_new")

    def test_above_threshold_with_existing_incident_merges(self):
        incident = Incident(incident_id="i1", subject_id="s1", status="open", opened_at=_NOW)
        self.assertEqual(decide_incident_transition(incident, 90, incident_score_threshold=70), "merge_into_existing")

    def test_custom_threshold_respected(self):
        self.assertEqual(decide_incident_transition(None, 35, incident_score_threshold=30), "open_new")


class TestDecideIncidentClosure(unittest.TestCase):
    def test_closes_when_normal_and_quiet_long_enough(self):
        self.assertTrue(decide_incident_closure("normal", 3600, close_after_quiet_seconds=3600))

    def test_stays_open_when_not_quiet_long_enough(self):
        self.assertFalse(decide_incident_closure("normal", 100, close_after_quiet_seconds=3600))

    def test_stays_open_when_level_is_not_normal_regardless_of_quiet_time(self):
        self.assertFalse(decide_incident_closure("suspicious", 999999, close_after_quiet_seconds=3600))


class TestRedactFields(unittest.TestCase):
    def test_redacts_configured_fields_case_insensitively(self):
        data = {"Authorization": "Bearer x", "Cookie": "session=1", "path": "/admin"}
        redacted = redact_fields(data, ("authorization", "cookie"))
        self.assertEqual(redacted["Authorization"], "***REDACTED***")
        self.assertEqual(redacted["Cookie"], "***REDACTED***")
        self.assertEqual(redacted["path"], "/admin")

    def test_default_fields_cover_password_token_authorization_cookie(self):
        data = {"password": "x", "token": "y", "authorization": "z", "cookie": "w", "user": "kept"}
        redacted = redact_fields(data)
        self.assertTrue(all(redacted[k] == "***REDACTED***" for k in ("password", "token", "authorization", "cookie")))
        self.assertEqual(redacted["user"], "kept")


class TestHashPayload(unittest.TestCase):
    def test_deterministic_and_never_reversible_in_practice(self):
        digest = hash_payload(b"union select * from users")
        self.assertEqual(len(digest), 64)  # sha256 hex digest
        self.assertEqual(digest, hash_payload(b"union select * from users"))

    def test_different_payloads_hash_differently(self):
        self.assertNotEqual(hash_payload(b"a"), hash_payload(b"b"))


class TestValidatePlaybookAction(unittest.TestCase):
    def test_allowed_action_is_valid(self):
        playbook = DefensePlaybook(scope="source", actions=("assign_deception", "enrich_log"))
        self.assertTrue(validate_playbook_action("assign_deception", playbook))

    def test_action_outside_playbook_is_invalid(self):
        playbook = DefensePlaybook(scope="source", actions=("enrich_log",))
        self.assertFalse(validate_playbook_action("delay", playbook))


def _finding_with_pack(pack: str) -> WafFinding:
    return WafFinding(rule_id="R1", pack=pack, description="", severity=Severity.HIGH, weight=10, scope="path")


class TestAttackClassForWafDecision(unittest.TestCase):
    def test_sqli_pack_maps_to_sqli(self):
        decision = WafDecision(action="block", status_code=403, score=10, findings=(_finding_with_pack("body-sqli"),))
        self.assertEqual(attack_class_for_waf_decision(decision), "sqli")

    def test_xss_pack_maps_to_xss(self):
        decision = WafDecision(action="log", status_code=None, score=10, findings=(_finding_with_pack("body-xss"),))
        self.assertEqual(attack_class_for_waf_decision(decision), "xss")

    def test_sensitive_paths_pack_maps_to_scan(self):
        decision = WafDecision(action="log", status_code=None, score=10, findings=(_finding_with_pack("sensitive-paths"),))
        self.assertEqual(attack_class_for_waf_decision(decision), "scan")

    def test_unknown_pack_falls_back_to_unknown(self):
        decision = WafDecision(action="log", status_code=None, score=10, findings=(_finding_with_pack("something-else"),))
        self.assertEqual(attack_class_for_waf_decision(decision), "unknown")

    def test_no_findings_falls_back_to_unknown(self):
        decision = WafDecision(action="allow", status_code=None, score=0, findings=())
        self.assertEqual(attack_class_for_waf_decision(decision), "unknown")


class TestBuildObservationFromWafDecision(unittest.TestCase):
    def test_builds_a_waf_decision_observation(self):
        decision = WafDecision(action="block", status_code=403, score=10, findings=(_finding_with_pack("body-sqli"),))
        observation = build_observation_from_waf_decision("203.0.113.1:abc", decision, _NOW)
        self.assertEqual(observation.subject_id, "203.0.113.1:abc")
        self.assertEqual(observation.kind, "waf_decision")
        self.assertEqual(observation.attack_class, "sqli")
        self.assertEqual(observation.score_delta, 10)
        self.assertIn("R1", observation.detail)
        self.assertNotIn("union select", observation.detail.lower())


class TestExtractIndicators(unittest.TestCase):
    def _incident(self, observations) -> Incident:
        return Incident(
            incident_id="i1", subject_id="203.0.113.1:abcd1234", status="open", opened_at=_NOW,
            observations=tuple(observations),
        )

    def test_no_observations_yields_no_indicators(self):
        self.assertEqual(extract_indicator_candidates(self._incident([])), [])

    def test_extracts_ip_and_user_agent_from_subject_id(self):
        observation = ThreatObservation(
            subject_id="203.0.113.1:abcd1234", observed_at=_NOW, kind="waf_decision",
            attack_class="sqli", score_delta=10, detail="WAF block",
        )
        candidates = extract_indicator_candidates(self._incident([observation]))
        kinds = {c.kind for c in candidates}
        self.assertEqual(kinds, {"ip", "user_agent"})
        ip_candidate = next(c for c in candidates if c.kind == "ip")
        self.assertEqual(ip_candidate.value, "203.0.113.1")
        ua_candidate = next(c for c in candidates if c.kind == "user_agent")
        self.assertEqual(ua_candidate.value, "abcd1234")

    def test_confidence_is_clamped_to_100(self):
        observations = [
            ThreatObservation(
                subject_id="203.0.113.1:abcd1234", observed_at=_NOW, kind="waf_decision",
                attack_class="sqli", score_delta=80, detail="",
            ),
            ThreatObservation(
                subject_id="203.0.113.1:abcd1234", observed_at=_NOW, kind="waf_decision",
                attack_class="sqli", score_delta=80, detail="",
            ),
        ]
        candidates = extract_indicator_candidates(self._incident(observations))
        self.assertTrue(all(c.confidence == 100 for c in candidates))

    def test_extract_indicators_assigns_ids_via_injected_factory(self):
        observation = ThreatObservation(
            subject_id="203.0.113.1:abcd1234", observed_at=_NOW, kind="waf_decision",
            attack_class="sqli", score_delta=10, detail="",
        )
        counter = iter(("id-1", "id-2"))
        indicators = extract_indicators(self._incident([observation]), id_factory=lambda: next(counter))
        self.assertEqual({i.indicator_id for i in indicators}, {"id-1", "id-2"})
        self.assertTrue(all(i.incident_id == "i1" for i in indicators))


class TestBuildPlaybook(unittest.TestCase):
    def test_translates_war_mode_config_into_playbook(self):
        war_mode = WarModeConfig(
            scope="instance", actions=("delay", "enrich_log"),
        )
        playbook = build_playbook(war_mode)
        self.assertEqual(playbook.scope, "instance")
        self.assertEqual(playbook.actions, ("delay", "enrich_log"))
        self.assertEqual(playbook.suspicious_score, war_mode.thresholds.suspicious_score)
        self.assertEqual(playbook.hostile_score, war_mode.thresholds.hostile_score)
        self.assertEqual(playbook.incident_score, war_mode.thresholds.incident_score)
        self.assertTrue(validate_playbook_action("delay", playbook))
        self.assertFalse(validate_playbook_action("rate_limit", playbook))


class TestIsSourceMarked(unittest.TestCase):
    def test_normal_is_not_marked(self):
        self.assertFalse(is_source_marked("normal"))

    def test_suspicious_hostile_contained_are_marked(self):
        for level in ("suspicious", "hostile", "contained"):
            self.assertTrue(is_source_marked(level))


class TestComputeSlowdownDelayMs(unittest.TestCase):
    def test_zero_jitter_fraction_returns_minimum(self):
        delay = compute_slowdown_delay_ms(0.0, minimum_ms=250, maximum_ms=1500, jitter_ms=200)
        self.assertEqual(delay, 250)

    def test_full_jitter_fraction_adds_full_jitter(self):
        delay = compute_slowdown_delay_ms(1.0, minimum_ms=250, maximum_ms=1500, jitter_ms=200)
        self.assertEqual(delay, 450)

    def test_never_exceeds_maximum_even_with_large_jitter(self):
        delay = compute_slowdown_delay_ms(1.0, minimum_ms=1400, maximum_ms=1500, jitter_ms=1000)
        self.assertEqual(delay, 1500)

    def test_out_of_range_jitter_fraction_is_clamped(self):
        low = compute_slowdown_delay_ms(-1.0, minimum_ms=250, maximum_ms=1500, jitter_ms=200)
        high = compute_slowdown_delay_ms(2.0, minimum_ms=250, maximum_ms=1500, jitter_ms=200)
        self.assertEqual(low, 250)
        self.assertEqual(high, 450)


if __name__ == "__main__":
    unittest.main()
