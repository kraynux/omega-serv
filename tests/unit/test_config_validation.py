# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import is_safe_relative_path, validate_config


class TestIsSafeRelativePath(unittest.TestCase):
    def test_relative_path_is_safe(self):
        self.assertTrue(is_safe_relative_path("var/log"))

    def test_absolute_path_is_unsafe(self):
        self.assertFalse(is_safe_relative_path("/etc/passwd"))

    def test_traversal_is_unsafe(self):
        self.assertFalse(is_safe_relative_path("../outside"))
        self.assertFalse(is_safe_relative_path("var/../../etc"))

    def test_empty_is_unsafe(self):
        self.assertFalse(is_safe_relative_path(""))

    def test_nul_byte_is_unsafe(self):
        self.assertFalse(is_safe_relative_path("var/log\x00"))


class TestValidateConfig(unittest.TestCase):
    def test_default_config_is_valid(self):
        self.assertEqual(validate_config(OmegaServConfig()), [])

    def test_invalid_port_is_rejected(self):
        config = OmegaServConfig.from_dict({"server": {"port": 70000}})
        errors = validate_config(config)
        self.assertTrue(any("port" in e for e in errors))

    def test_unknown_method_is_rejected(self):
        config = OmegaServConfig.from_dict({"security": {"allowed_methods": ["GET", "FOOBAR"]}})
        errors = validate_config(config)
        self.assertTrue(any("allowed_methods" in e for e in errors))

    def test_invalid_csp_mode_is_rejected(self):
        config = OmegaServConfig.from_dict({"security": {"csp_mode": "disabled"}})
        errors = validate_config(config)
        self.assertTrue(any("csp_mode" in e for e in errors))

    def test_unknown_option_is_rejected(self):
        config = OmegaServConfig.from_dict({"options": {"cgi": {"enabled": True}}})
        errors = validate_config(config)
        self.assertTrue(any("cgi" in e for e in errors))

    def test_active_defense_is_a_known_option(self):
        # plan_active_defense_omega_serv.md, Phase 0 - flag maitre
        # active_defense.enabled: false, jamais rejete comme option
        # inconnue.
        config = OmegaServConfig.from_dict({"options": {"active_defense": {"enabled": False}}})
        errors = validate_config(config)
        self.assertFalse(any("active_defense" in e for e in errors))

    def test_disabled_active_defense_is_never_structurally_validated(self):
        config = OmegaServConfig.from_dict({"options": {"active_defense": {"enabled": False, "mode": "bogus"}}})
        self.assertEqual(validate_config(config), [])

    def test_enabled_active_defense_structural_errors_surface_here(self):
        # plan_active_defense_omega_serv.md, Phase 4/5 - validate_active_
        # defense_config() existait depuis la Phase 0 mais n'etait jamais
        # invoquee depuis le pipeline de validation reel (omega-serv
        # config check/init) - corrige ici.
        config = OmegaServConfig.from_dict({"options": {"active_defense": {"enabled": True, "mode": "bogus"}}})
        errors = validate_config(config)
        self.assertTrue(any("options.active_defense" in e and "mode" in e for e in errors))

    def test_decoy_zone_reusing_a_production_upstream_is_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {
                "reverse_proxy": {
                    "enabled": True,
                    "zones": [{"url_prefix": "/app", "upstreams": [{"host": "10.0.0.5", "port": 9000}]}],
                },
                "active_defense": {
                    "enabled": True,
                    "deception": {
                        "decoy_zones": {"decoy-1": {"upstreams": [{"host": "10.0.0.5", "port": 9000}]}},
                    },
                },
            },
        })
        errors = validate_config(config)
        self.assertTrue(any("decoy_zones.decoy-1" in e and "10.0.0.5" in e for e in errors))

    def test_decoy_zone_with_a_distinct_upstream_is_not_rejected_by_the_collision_check(self):
        config = OmegaServConfig.from_dict({
            "options": {
                "reverse_proxy": {
                    "enabled": True,
                    "zones": [{"url_prefix": "/app", "upstreams": [{"host": "10.0.0.5", "port": 9000}]}],
                },
                "active_defense": {
                    "enabled": True,
                    "deception": {
                        "decoy_zones": {"decoy-1": {"upstreams": [{"host": "10.0.0.9", "port": 9001}]}},
                    },
                },
            },
        })
        errors = validate_config(config)
        self.assertFalse(any("decoy_zones" in e for e in errors))

    def test_unsupported_version_is_rejected(self):
        config = OmegaServConfig.from_dict({"version": 2})
        errors = validate_config(config)
        self.assertTrue(any("version" in e for e in errors))

    def test_absolute_path_in_paths_is_rejected(self):
        config = OmegaServConfig.from_dict({"paths": {"webroot": "/var/www/html"}})
        errors = validate_config(config)
        self.assertTrue(any("paths.webroot" in e for e in errors))

    def test_non_positive_limit_is_rejected(self):
        config = OmegaServConfig.from_dict({"server": {"max_connections": 0}})
        errors = validate_config(config)
        self.assertTrue(any("max_connections" in e for e in errors))

    def test_non_positive_shutdown_grace_period_is_rejected(self):
        config = OmegaServConfig.from_dict({"server": {"shutdown_grace_period_seconds": 0}})
        errors = validate_config(config)
        self.assertTrue(any("shutdown_grace_period_seconds" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
