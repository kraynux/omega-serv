import unittest

from omega_serv.domain.security.waf.config import WafConfig, parse_waf_config, validate_waf_config


class TestParseWafConfig(unittest.TestCase):
    def test_defaults_are_safe(self):
        config = parse_waf_config({})
        self.assertEqual(config.mode, "log-only")
        self.assertEqual(config.engine, "python")
        self.assertEqual(config.on_internal_error, "fail-open")
        self.assertIn("/healthz", config.exclusions.path_prefixes)

    def test_full_example_parses(self):
        settings = {
            "engine": "python",
            "mode": "block",
            "inspect": {"path": True, "query": True, "headers": False, "body_methods": ["POST"], "body_max_inspect_bytes": 1024, "decode_depth": 2},
            "scoring": {"block_threshold": 5, "high_score_threshold": 8, "response_status": 403},
            "rate_limit": {"enabled": True, "algorithm": "token_bucket", "global": {"key": "client_ip", "requests": 60, "window_seconds": 60, "response_status": 429}},
            "reputation": {"enabled": True, "suspicious_threshold": 3, "window_seconds": 300, "auto_block": False, "auto_block_duration_seconds": 3600},
            "blocklist": {"enabled": True, "path": "secure/waf/blocklist.json"},
            "rules": {"paths": ["secure/waf/rules/core.json"]},
            "exclusions": {"extensions": [".ico"], "path_prefixes": ["/healthz"]},
            "logging": {"path": "var/log/waf-alerts.log", "mask_headers": ["Authorization"]},
        }
        config = parse_waf_config(settings)
        self.assertEqual(config.mode, "block")
        self.assertEqual(config.scoring.block_threshold, 5)
        self.assertTrue(config.rate_limit.enabled)
        self.assertEqual(config.rate_limit.global_.requests, 60)
        self.assertEqual(config.rule_paths, ("secure/waf/rules/core.json",))
        self.assertIn("authorization", config.logging.mask_headers)


class TestValidateWafConfig(unittest.TestCase):
    def test_valid_config_with_rule_paths_passes(self):
        config = parse_waf_config({"rules": {"paths": ["secure/waf/rules/core.json"]}})
        self.assertEqual(validate_waf_config(config), [])

    def test_empty_rule_paths_rejected(self):
        config = parse_waf_config({})
        errors = validate_waf_config(config)
        self.assertTrue(any("rules.paths" in e for e in errors))

    def test_invalid_mode_rejected(self):
        config = WafConfig(mode="allow-all")  # type: ignore[arg-type]
        errors = validate_waf_config(config)
        self.assertTrue(any("mode" in e for e in errors))

    def test_zero_block_threshold_rejected(self):
        config = parse_waf_config({"rules": {"paths": ["x"]}, "scoring": {"block_threshold": 0}})
        errors = validate_waf_config(config)
        self.assertTrue(any("block_threshold" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
