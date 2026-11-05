"""Domaine RIPOSTE, lot 3 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.3-3.5) : episodes, retours, paliers,
decision unique et explicable, scenarios prets."""
import itertools
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.domain.security.riposte.config import (
    DAY,
    DEFAULT_TIERS_SECONDS,
    HOUR,
    RiposteConfig,
    RipostePolicy,
    validate_riposte_config,
)
from omega_serv.domain.security.riposte.decide import SafetyContext, decide
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.domain.security.riposte.history import (
    MAX_EPISODES,
    PastAction,
    SourceHistory,
    apply_event,
    episodes_since,
    forget_before,
    next_tier_index,
    record_action,
)
from omega_serv.domain.security.riposte.scenarios import SCENARIOS, find_scenario

T0 = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
IP = "203.0.113.7"
SAFE = SafetyContext(exempt_networks=())


_EVENT_IDS = itertools.count(1)


def _event(kind="attack", at=T0, attack_class="scan", level=None):
    return ObservedEvent(source="waf", event_id=f"e{next(_EVENT_IDS)}", kind=kind, timestamp=at, remote_ip=IP,
                         attack_class=attack_class if kind == "attack" else None, level=level, score=8)


def _apply(history, *events, gap=HOUR):
    started = []
    for event in events:
        history, new = apply_event(history, event, episode_gap_seconds=gap)
        started.append(new)
    return history, started


class TestEpisodes(unittest.TestCase):
    def test_silence_longer_than_the_gap_starts_a_new_episode(self):
        history, started = _apply(SourceHistory(IP), _event(at=T0), _event(at=T0 + timedelta(minutes=50)),
                                  _event(at=T0 + timedelta(minutes=50) + timedelta(hours=1, seconds=1)))
        self.assertEqual(started, [True, False, True])
        self.assertEqual(len(history.episodes), 2)
        self.assertEqual(history.episodes[0].attacks, 2)

    def test_blocklist_hits_never_create_or_extend_activity(self):
        history, started = _apply(SourceHistory(IP), _event(kind="blocklist_hit"))
        self.assertEqual((history.episodes, started), ((), [False]))
        history, _ = _apply(history, _event(at=T0), _event(kind="blocklist_hit", at=T0 + timedelta(hours=5)))
        self.assertEqual(history.current_episode.blocklist_hits, 1)
        self.assertEqual(history.current_episode.last_seen_at, T0)  # jamais prolonge par un refus

    def test_escalation_enriches_the_current_episode_only(self):
        history, _ = _apply(SourceHistory(IP), _event(kind="threat_escalated", level="hostile"))
        self.assertEqual(history.episodes, ())
        history, _ = _apply(history, _event(), _event(kind="threat_escalated", level="hostile"),
                            _event(kind="threat_escalated", level="suspicious"))
        self.assertEqual(history.current_episode.max_level, "hostile")  # jamais redescendu

    def test_activity_after_an_action_ends_is_a_return(self):
        history, _ = _apply(SourceHistory(IP), _event(at=T0))
        history = record_action(history, PastAction(T0, T0 + timedelta(minutes=10), "p", 0))
        history, started = _apply(history, _event(at=T0 + timedelta(minutes=11)))
        self.assertEqual(started, [True])

    def test_classes_and_decoy_hits_accumulate(self):
        history, _ = _apply(SourceHistory(IP), _event(attack_class="scan"), _event(attack_class="sqli"),
                            _event(attack_class="scan"), _event(kind="decoy_hit"))
        episode = history.current_episode
        self.assertEqual(episode.attack_classes, ("scan", "sqli"))
        self.assertEqual(episode.decoy_hits, 1)

    def test_bounded_and_forgettable(self):
        history = SourceHistory(IP)
        for i in range(MAX_EPISODES + 10):
            history, _ = _apply(history, _event(at=T0 + timedelta(hours=2 * i)))
        self.assertEqual(len(history.episodes), MAX_EPISODES)
        forgotten = forget_before(history, T0 + timedelta(days=365))
        self.assertEqual(forgotten.episodes, ())

    def test_round_trip(self):
        history, _ = _apply(SourceHistory(IP), _event(), _event(kind="threat_escalated", level="hostile"))
        history = record_action(history, PastAction(T0, T0 + timedelta(hours=1), "p", 0, counts_for_recidive=False))
        self.assertEqual(SourceHistory.from_dict(history.to_dict()), history)


class TestTiers(unittest.TestCase):
    def _with_actions(self, *ages_days, counts=True):
        history = SourceHistory(IP)
        for age in ages_days:
            taken = T0 - timedelta(days=age)
            history = record_action(history, PastAction(taken, taken + timedelta(hours=1), "p", 0, counts))
        return history

    def test_tier_grows_with_actions_in_the_window_and_is_capped(self):
        self.assertEqual(next_tier_index(self._with_actions(), T0, recidive_window_seconds=30 * DAY, tier_count=4), 0)
        self.assertEqual(next_tier_index(self._with_actions(1, 2), T0, recidive_window_seconds=30 * DAY, tier_count=4), 2)
        self.assertEqual(next_tier_index(self._with_actions(*range(10)), T0, recidive_window_seconds=30 * DAY,
                                         tier_count=4), 3)

    def test_thirty_quiet_days_go_back_to_the_first_tier(self):
        self.assertEqual(next_tier_index(self._with_actions(31, 40), T0, recidive_window_seconds=30 * DAY, tier_count=4), 0)

    def test_lifted_false_positive_does_not_count(self):
        self.assertEqual(next_tier_index(self._with_actions(1, counts=False), T0, recidive_window_seconds=30 * DAY,
                                         tier_count=4), 0)


def _config(*policies, **overrides):
    return RiposteConfig(policies=policies, **overrides)


def _scan_policy(**overrides):
    values = {"id": "scan", "name": "Scan", "attack_classes": ("scan",), "returns": 3, "within_seconds": 7 * DAY}
    values.update(overrides)
    return RipostePolicy(**values)


def _history_with_episodes(count, attack_class="scan"):
    history = SourceHistory(IP)
    for i in range(count):
        history, _ = _apply(history, _event(at=T0 - timedelta(hours=2 * (count - 1 - i)), attack_class=attack_class))
    return history


class TestDecide(unittest.TestCase):
    def _decide(self, history, config, safety=SAFE, event=None):
        return decide(history, event or _event(at=T0), config, safety, T0)

    def test_third_episode_matches_with_the_first_tier(self):
        decision = self._decide(_history_with_episodes(3), _config(_scan_policy()))
        self.assertEqual(decision.status, "matched")
        self.assertEqual((decision.policy_id, decision.tier_index, decision.duration_seconds), ("scan", 0, HOUR))
        codes = [r.code for r in decision.reasons]
        self.assertEqual(codes[:2], ["event", "exemptions_checked"])
        self.assertIn("policy_matched", codes)
        self.assertEqual(decision.reasons[-1].param("duration"), HOUR)

    def test_not_enough_returns_is_explained(self):
        decision = self._decide(_history_with_episodes(2), _config(_scan_policy()))
        self.assertEqual(decision.status, "observed")
        unmet = next(r for r in decision.reasons if r.code == "unmet_returns")
        self.assertEqual((unmet.param("have"), unmet.param("need")), (2, 3))

    def test_wrong_class_level_and_decoy_conditions(self):
        history = _history_with_episodes(3, attack_class="sqli")
        self.assertEqual(self._decide(history, _config(_scan_policy())).reasons[-2].code, "unmet_attack_class")
        level = _scan_policy(attack_classes=(), min_ad_level="hostile")
        self.assertEqual(self._decide(history, _config(level)).reasons[-2].code, "unmet_level")
        decoy = _scan_policy(attack_classes=(), decoy_hits=2)
        self.assertEqual(self._decide(history, _config(decoy)).reasons[-2].code, "unmet_decoy_hits")

    def test_first_matching_policy_in_configuration_order_wins(self):
        first = _scan_policy(id="a", returns=1)
        second = _scan_policy(id="b", returns=1)
        self.assertEqual(self._decide(_history_with_episodes(1), _config(first, second)).policy_id, "a")
        self.assertEqual(self._decide(_history_with_episodes(1), _config(_scan_policy(id="a", returns=1, enabled=False),
                                                                          second)).policy_id, "b")

    def test_exempt_networks_win_over_everything(self):
        safety = SafetyContext(exempt_networks=("203.0.113.0/24",))
        decision = self._decide(_history_with_episodes(3), _config(_scan_policy()), safety)
        self.assertEqual(decision.status, "rejected_by_safety")
        self.assertEqual(decision.reasons[-1].param("network"), "203.0.113.0/24")

    def test_ipv4_mapped_ipv6_cannot_bypass_an_exemption(self):
        history = SourceHistory("::ffff:203.0.113.7", episodes=_history_with_episodes(3).episodes)
        safety = SafetyContext(exempt_networks=("203.0.113.0/24",))
        self.assertEqual(self._decide(history, _config(_scan_policy()), safety).status, "rejected_by_safety")

    def test_emergency_stop(self):
        decision = self._decide(_history_with_episodes(3), _config(_scan_policy()), SafetyContext((), emergency_stop=True))
        self.assertEqual(decision.status, "stopped")

    def test_one_action_per_episode(self):
        history = record_action(_history_with_episodes(3), PastAction(T0, T0 + timedelta(hours=1), "scan", 0))
        self.assertEqual(self._decide(history, _config(_scan_policy())).reasons[-1].code, "already_acted_this_episode")

    def test_blocklist_hit_never_decides(self):
        decision = self._decide(_history_with_episodes(3), _config(_scan_policy()), event=_event(kind="blocklist_hit"))
        self.assertEqual(decision.reasons[-1].code, "not_a_deciding_event")

    def test_caps(self):
        per_source = self._decide(_history_with_episodes(3), _config(_scan_policy()), SafetyContext((), active_for_source=1))
        self.assertEqual(per_source.reasons[-1].code, "source_already_has_action")
        total = self._decide(_history_with_episodes(3), _config(_scan_policy(), max_active_bans=5),
                             SafetyContext((), active_total=5))
        self.assertEqual(total.reasons[-1].code, "max_active_bans_reached")

    def test_tier_progresses_with_past_actions(self):
        history = _history_with_episodes(3)
        for days in (10, 5):
            taken = T0 - timedelta(days=days)
            history = SourceHistory(IP, episodes=history.episodes,
                                    actions=(*history.actions, PastAction(taken, taken + timedelta(hours=1), "scan", 0)))
        decision = self._decide(history, _config(_scan_policy()))
        self.assertEqual((decision.tier_index, decision.duration_seconds), (2, DEFAULT_TIERS_SECONDS[2]))

    def test_policy_tiers_override_the_global_ones(self):
        decision = self._decide(_history_with_episodes(3), _config(_scan_policy(tiers_seconds=(600, 1200))))
        self.assertEqual(decision.duration_seconds, 600)

    def test_decoy_action(self):
        policy = _scan_policy(action="decoy", decoy_profile="fake_api", decoy_duration_seconds=DAY, returns=1)
        decision = self._decide(_history_with_episodes(1), _config(policy))
        self.assertEqual((decision.action, decision.decoy_profile, decision.duration_seconds), ("decoy", "fake_api", DAY))
        self.assertIsNone(decision.tier_index)


class TestScenarios(unittest.TestCase):
    def test_every_scenario_is_valid_without_any_risk_confirmation(self):
        config = RiposteConfig(policies=tuple(s.policy for s in SCENARIOS))
        self.assertEqual(validate_riposte_config(config, decoy_profile_names=frozenset({"fake_admin", "fake_api"})), [])
        for scenario in SCENARIOS:
            self.assertEqual(scenario.policy.confirmed_risks, ())
            self.assertEqual(scenario.policy.origin, f"scenario:{scenario.id}")
            self.assertTrue(scenario.name and scenario.for_whom and scenario.what_it_does and scenario.what_it_does_not)

    def test_find(self):
        self.assertEqual(find_scenario("scan-recidive").id, "scan-recidive")
        self.assertIsNone(find_scenario("inconnu"))

    def test_episodes_since(self):
        self.assertEqual(episodes_since(_history_with_episodes(3), T0 - timedelta(hours=3)), 2)


if __name__ == "__main__":
    unittest.main()
