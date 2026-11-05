"""Configuration RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.4, lot 2) : defauts valides par
l'utilisateur, aller-retour JSON exact, garde-fous de validation."""
import unittest

from omega_serv.domain.security.riposte.config import (
    DAY,
    DEFAULT_TIERS_SECONDS,
    HOUR,
    RiposteConfig,
    RipostePolicy,
    parse_riposte_config,
    validate_riposte_config,
)


def _policy(**data):
    base = {"id": "scan-recidive", "name": "Scanner récidiviste", "when": {"attack_classes": ["scan"], "returns": 3}}
    base.update(data)
    return base


class TestDefaults(unittest.TestCase):
    def test_validated_defaults(self):
        config = parse_riposte_config({})
        self.assertEqual(DEFAULT_TIERS_SECONDS, (HOUR, 6 * HOUR, DAY, 7 * DAY))
        self.assertEqual(config.tiers_seconds, DEFAULT_TIERS_SECONDS)
        self.assertEqual(config.recidive_window_seconds, 30 * DAY)
        self.assertEqual(config.episode_gap_seconds, HOUR)
        self.assertEqual(config.history_retention_seconds, 90 * DAY)
        self.assertEqual(config.max_active_bans, 100)
        self.assertEqual(config.policies, ())
        self.assertEqual(validate_riposte_config(config), [])

    def test_policy_defaults_are_the_prudent_ones(self):
        policy = RipostePolicy.from_dict(_policy())
        self.assertEqual(policy.scope, "ip")
        self.assertEqual(policy.action, "local_ban")
        self.assertIsNone(policy.tiers_seconds)  # paliers globaux
        self.assertEqual(policy.max_active_per_source, 1)


class TestRoundTrip(unittest.TestCase):
    def test_to_dict_is_the_exact_inverse_of_from_dict(self):
        for data in (
            _policy(),
            _policy(when={"min_ad_level": "hostile", "attack_classes": ["sqli", "xss"], "returns": 2, "within_seconds": 86400},
                    then={"action": "local_and_network_ban", "tiers_seconds": [1800, 7200]}, enabled=False,
                    origin="scenario:injections-repetees"),
            _policy(then={"action": "decoy", "decoy_profile": "fake_admin", "decoy_duration_seconds": 3600},
                    confirmed_risks=["suspicious_level"], when={"min_ad_level": "suspicious", "returns": 1}),
        ):
            policy = RipostePolicy.from_dict(data)
            self.assertEqual(RipostePolicy.from_dict(policy.to_dict()), policy)


class TestValidation(unittest.TestCase):
    def _errors(self, settings, profiles=frozenset({"fake_admin"})):
        return validate_riposte_config(parse_riposte_config(settings), decoy_profile_names=profiles)

    def test_valid_policy(self):
        self.assertEqual(self._errors({"policies": [_policy()]}), [])

    def test_tiers_must_be_positive_and_increasing(self):
        self.assertTrue(self._errors({"tiers_seconds": [6 * HOUR, HOUR]}))
        self.assertTrue(self._errors({"tiers_seconds": [0, HOUR]}))
        self.assertTrue(self._errors({"tiers_seconds": []}))

    def test_tier_beyond_seven_days_needs_confirmation(self):
        self.assertTrue(self._errors({"tiers_seconds": [HOUR, 30 * DAY]}))  # jamais au niveau global
        too_long = _policy(then={"action": "local_ban", "tiers_seconds": [HOUR, 30 * DAY]})
        self.assertTrue(self._errors({"policies": [too_long]}))
        self.assertEqual(self._errors({"policies": [{**too_long, "confirmed_risks": ["long_duration"]}]}), [])

    def test_suspicious_level_needs_confirmation(self):
        early = _policy(when={"min_ad_level": "suspicious", "returns": 1})
        self.assertTrue(self._errors({"policies": [early]}))
        self.assertEqual(self._errors({"policies": [{**early, "confirmed_risks": ["suspicious_level"]}]}), [])

    def test_unknown_values_are_rejected(self):
        self.assertTrue(self._errors({"policies": [_policy(when={"attack_classes": ["ddos"], "returns": 1})]}))
        self.assertTrue(self._errors({"policies": [_policy(when={"min_ad_level": "furieux", "returns": 1})]}))
        self.assertTrue(self._errors({"policies": [_policy(then={"action": "contre-attaque"})]}))
        self.assertTrue(self._errors({"policies": [_policy(scope="network")]}))
        self.assertTrue(self._errors({"policies": [_policy(confirmed_risks=["tout"])]}))

    def test_ids_are_unique_and_well_formed(self):
        self.assertTrue(self._errors({"policies": [_policy(), _policy()]}))
        self.assertTrue(self._errors({"policies": [_policy(id="Pas Bon")]}))
        self.assertTrue(self._errors({"policies": [_policy(name="  ")]}))

    def test_decoy_needs_a_configured_profile_and_a_bounded_duration(self):
        self.assertTrue(self._errors({"policies": [_policy(then={"action": "decoy"})]}))
        self.assertTrue(self._errors({"policies": [_policy(then={"action": "decoy", "decoy_profile": "fake_cms"})]}))
        ok = _policy(then={"action": "decoy", "decoy_profile": "fake_admin"})
        self.assertEqual(self._errors({"policies": [ok]}), [])
        zero = _policy(then={"action": "decoy", "decoy_profile": "fake_admin", "decoy_duration_seconds": 0})
        self.assertTrue(self._errors({"policies": [{**zero, "confirmed_risks": ["long_duration"]}]}))

    def test_global_bounds(self):
        self.assertTrue(self._errors({"max_active_bans": 0}))
        self.assertTrue(self._errors({"max_active_bans": 10_001}))
        self.assertTrue(self._errors({"episode_gap_seconds": 0}))
        self.assertTrue(self._errors({"exemptions": ["pas-un-reseau"]}))
        self.assertEqual(self._errors({"exemptions": ["198.51.100.0/24", "2001:db8::/32"]}), [])

    def test_returns_must_be_at_least_one(self):
        self.assertTrue(self._errors({"policies": [_policy(when={"returns": 0})]}))

    def test_dataclass_defaults_match_parse(self):
        self.assertEqual(parse_riposte_config({}), RiposteConfig())


if __name__ == "__main__":
    unittest.main()
