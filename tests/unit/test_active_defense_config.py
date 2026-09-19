"""plan_active_defense_omega_serv.md, Phase 0 - meme discipline que
test_config_validation.py (WAF) : parse_active_defense_config() ne
touche jamais le filesystem, validate_active_defense_config() est une
fonction pure retournant une liste d'erreurs."""
import unittest

from omega_serv.domain.routing.proxy_zone import ProxyZone, UpstreamTarget
from omega_serv.domain.security.active_defense.config import (
    ActiveDefenseConfig,
    parse_active_defense_config,
    validate_active_defense_config,
    validate_decoy_zone,
)
from omega_serv.domain.security.active_defense.value_objects import KNOWN_FIXTURE_PROFILE_NAMES


class TestParseActiveDefenseConfig(unittest.TestCase):
    def test_defaults_when_settings_empty(self):
        config = parse_active_defense_config({})
        self.assertEqual(config.mode, "monitor")
        self.assertEqual(config.state_ttl_seconds, 7200)
        self.assertFalse(config.deception.enabled)
        self.assertFalse(config.war_mode.enabled)
        self.assertFalse(config.ioc.enabled)

    def test_parses_full_shape_from_the_plan_document(self):
        settings = {
            "mode": "enforce",
            "state_ttl_seconds": 3600,
            "storage": {"database": "var/lib/x.sqlite3", "export_dir": "var/lib/exports"},
            "logging": {"enhanced_capture": True, "max_body_bytes": 2048, "redact_fields": ["password"]},
            "deception": {
                "enabled": True,
                "fallback": "reject",
                "assignments_ttl_seconds": 1800,
                "profiles": {
                    "fake_admin": {"enabled": True, "match_attack_classes": ["scan", "credential_stuffing"]},
                },
            },
            "war_mode": {
                "enabled": True,
                "scope": "instance",
                "actions": ["delay"],
                "thresholds": {"suspicious_score": 20, "hostile_score": 50, "incident_score": 65},
                "slowdown": {"enabled": False, "minimum_ms": 100, "maximum_ms": 500, "jitter_ms": 50},
            },
            "ioc": {"enabled": True, "minimum_confidence": 80, "share_policy": "manual_export"},
        }
        config = parse_active_defense_config(settings)
        self.assertEqual(config.mode, "enforce")
        self.assertEqual(config.state_ttl_seconds, 3600)
        self.assertEqual(config.storage.database, "var/lib/x.sqlite3")
        self.assertTrue(config.logging.enhanced_capture)
        self.assertEqual(config.logging.max_body_bytes, 2048)
        self.assertTrue(config.deception.enabled)
        self.assertEqual(config.deception.fallback, "reject")
        self.assertIn("fake_admin", config.deception.profiles)
        self.assertEqual(config.deception.profiles["fake_admin"].match_attack_classes, ("scan", "credential_stuffing"))
        self.assertEqual(config.war_mode.scope, "instance")
        self.assertEqual(config.war_mode.thresholds.hostile_score, 50)
        self.assertFalse(config.war_mode.slowdown.enabled)
        self.assertEqual(config.ioc.minimum_confidence, 80)

    def test_default_war_mode_actions_use_real_action_types(self):
        """Correction Phase 4 : le defaut d'origine utilisait
        "assign_deception" (copie de l'exemple JSON du plan), qui n'a
        jamais ete une valeur de `ActionType` reelle - "redirect_to_decoy"
        l'est."""
        config = ActiveDefenseConfig()
        self.assertIn("redirect_to_decoy", config.war_mode.actions)
        self.assertNotIn("assign_deception", config.war_mode.actions)

    def test_default_log_path_is_separate_from_waf_and_production_logs(self):
        self.assertEqual(ActiveDefenseConfig().logging.log_path, "var/log/active-defense-enriched.jsonl")

    def test_parses_war_mode_rate_limit(self):
        settings = {"war_mode": {"rate_limit": {"requests": 3, "window_seconds": 30}}}
        config = parse_active_defense_config(settings)
        self.assertEqual(config.war_mode.rate_limit.requests, 3)
        self.assertEqual(config.war_mode.rate_limit.window_seconds, 30)

    def test_default_war_mode_rate_limit(self):
        config = ActiveDefenseConfig()
        self.assertEqual(config.war_mode.rate_limit.requests, 5)
        self.assertEqual(config.war_mode.rate_limit.window_seconds, 60)


class TestValidateActiveDefenseConfig(unittest.TestCase):
    def test_default_config_is_valid(self):
        self.assertEqual(validate_active_defense_config(ActiveDefenseConfig()), [])

    def test_rejects_invalid_mode(self):
        config = parse_active_defense_config({"mode": "bogus"})
        errors = validate_active_defense_config(config)
        self.assertTrue(any("mode" in e for e in errors))

    def test_rejects_non_positive_state_ttl(self):
        config = parse_active_defense_config({"state_ttl_seconds": 0})
        errors = validate_active_defense_config(config)
        self.assertTrue(any("state_ttl_seconds" in e for e in errors))

    def test_proxy_profile_without_zone_name_is_rejected(self):
        settings = {"deception": {"profiles": {"fake_admin": {"isolation_level": "proxy"}}}}
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("reverse_proxy_zone_name" in e for e in errors))

    def test_proxy_profile_referencing_an_unknown_decoy_zone_is_rejected(self):
        settings = {
            "deception": {
                "profiles": {
                    "fake_admin": {"isolation_level": "proxy", "reverse_proxy_zone_name": "decoy-zone"},
                },
            },
        }
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("decoy_zones" in e for e in errors))

    def test_proxy_profile_with_zone_name_is_valid(self):
        settings = {
            "deception": {
                "profiles": {
                    "fake_admin": {"isolation_level": "proxy", "reverse_proxy_zone_name": "decoy-zone"},
                },
                "decoy_zones": {
                    "decoy-zone": {"upstreams": [{"host": "127.0.0.1", "port": 9001}]},
                },
            },
        }
        config = parse_active_defense_config(settings)
        self.assertEqual(validate_active_defense_config(config), [])

    def test_fixture_profile_with_unknown_name_is_rejected(self):
        settings = {"deception": {"profiles": {"mon-leurre-perso": {"isolation_level": "fixture"}}}}
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("mon-leurre-perso" in e and "fixture" in e for e in errors))

    def test_all_known_fixture_names_are_valid(self):
        settings = {
            "deception": {
                "profiles": {name: {"isolation_level": "fixture"} for name in KNOWN_FIXTURE_PROFILE_NAMES},
            },
        }
        config = parse_active_defense_config(settings)
        self.assertEqual(validate_active_defense_config(config), [])

    def test_rejects_unknown_match_attack_class(self):
        settings = {"deception": {"profiles": {"fake_admin": {"match_attack_classes": ["sqli", "bogus"]}}}}
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("match_attack_classes" in e and "bogus" in e for e in errors))

    def test_known_match_attack_classes_are_valid(self):
        settings = {"deception": {"profiles": {"fake_admin": {"match_attack_classes": ["sqli", "scan"]}}}}
        config = parse_active_defense_config(settings)
        self.assertEqual(validate_active_defense_config(config), [])

    def test_rejects_thresholds_out_of_order(self):
        settings = {"war_mode": {"thresholds": {"suspicious_score": 60, "hostile_score": 30, "incident_score": 70}}}
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("thresholds" in e for e in errors))

    def test_default_contained_score_is_80(self):
        self.assertEqual(ActiveDefenseConfig().war_mode.thresholds.contained_score, 80)

    def test_rejects_contained_score_below_hostile_score(self):
        settings = {"war_mode": {"thresholds": {"hostile_score": 60, "contained_score": 50}}}
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("contained_score" in e for e in errors))

    def test_rejects_slowdown_minimum_above_maximum(self):
        settings = {"war_mode": {"slowdown": {"minimum_ms": 2000, "maximum_ms": 500}}}
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("slowdown" in e for e in errors))

    def test_rejects_out_of_range_confidence(self):
        config = parse_active_defense_config({"ioc": {"minimum_confidence": 150}})
        errors = validate_active_defense_config(config)
        self.assertTrue(any("minimum_confidence" in e for e in errors))

    def test_rejects_unknown_war_mode_action(self):
        config = parse_active_defense_config({"war_mode": {"actions": ["delay", "bogus_action"]}})
        errors = validate_active_defense_config(config)
        self.assertTrue(any("war_mode.actions" in e and "bogus_action" in e for e in errors))

    def test_known_war_mode_actions_are_valid(self):
        config = parse_active_defense_config(
            {"war_mode": {"actions": ["observe", "enrich_log", "delay", "rate_limit", "redirect_to_decoy", "create_incident", "export_ioc"]}},
        )
        self.assertEqual(validate_active_defense_config(config), [])

    def test_rejects_non_positive_rate_limit_requests(self):
        config = parse_active_defense_config({"war_mode": {"rate_limit": {"requests": 0}}})
        errors = validate_active_defense_config(config)
        self.assertTrue(any("rate_limit.requests" in e for e in errors))

    def test_rejects_non_positive_rate_limit_window(self):
        config = parse_active_defense_config({"war_mode": {"rate_limit": {"window_seconds": -1}}})
        errors = validate_active_defense_config(config)
        self.assertTrue(any("rate_limit.window_seconds" in e for e in errors))

    def test_rejects_invalid_decoy_zone(self):
        settings = {"deception": {"decoy_zones": {"z1": {"upstreams": []}}}}
        config = parse_active_defense_config(settings)
        errors = validate_active_defense_config(config)
        self.assertTrue(any("decoy_zones.z1" in e for e in errors))

    def test_valid_decoy_zone_alone_produces_no_error(self):
        settings = {"deception": {"decoy_zones": {"z1": {"upstreams": [{"host": "127.0.0.1", "port": 9001}]}}}}
        config = parse_active_defense_config(settings)
        self.assertEqual(validate_active_defense_config(config), [])


class TestValidateDecoyZone(unittest.TestCase):
    def test_zone_name_need_not_start_with_a_slash(self):
        zone = ProxyZone(url_prefix="decoy-1", upstreams=(UpstreamTarget(host="127.0.0.1", port=9001),))
        self.assertIsNone(validate_decoy_zone(zone))

    def test_rejects_zone_without_upstreams(self):
        zone = ProxyZone(url_prefix="decoy-1", upstreams=())
        self.assertIsNotNone(validate_decoy_zone(zone))

    def test_rejects_invalid_port(self):
        zone = ProxyZone(url_prefix="decoy-1", upstreams=(UpstreamTarget(host="127.0.0.1", port=0),))
        self.assertIsNotNone(validate_decoy_zone(zone))


if __name__ == "__main__":
    unittest.main()
