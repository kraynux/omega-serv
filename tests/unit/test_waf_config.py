import unittest

from omega_serv.domain.security.waf.config import (
    WafConfig,
    parse_waf_config,
    validate_waf_config,
    with_reputation_enabled_for_lists,
)


class TestParseWafConfig(unittest.TestCase):
    def test_defaults_are_safe(self):
        config = parse_waf_config({})
        self.assertEqual(config.mode, "log-only")
        self.assertEqual(config.engine, "python")
        self.assertEqual(config.on_internal_error, "fail-open")
        self.assertIn("/healthz", config.exclusions.path_prefixes)

    def test_keyword_lists_parsed(self):
        settings = {
            "rules": {
                "paths": ["secure/waf/rules/core.json"],
                "keyword_lists": [
                    {"id": "REFERER-SPAM", "scope": ["referer"], "file": "secure/waf/rules/keywords/referer-spam.txt", "weight": 3},
                ],
            },
        }
        config = parse_waf_config(settings)
        self.assertEqual(len(config.keyword_lists), 1)
        self.assertEqual(config.keyword_lists[0].id, "REFERER-SPAM")
        self.assertEqual(config.keyword_lists[0].scope, ("referer",))

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

    def test_magnet_paths_default_to_project_local_locations(self):
        config = parse_waf_config({})
        self.assertEqual(config.magnet.paths.blocklist_file, "var/lib/waf/magnet-blocklist.txt")
        self.assertEqual(config.blocklist.path, "var/lib/waf/blocklist.json")
        self.assertEqual(config.magnet.paths.rules_dir, "secure/waf/magnet-rules.d/")

    def test_legacy_default_paths_saved_explicitly_follow_the_new_default(self):
        # L'ecran WAF Magnet enregistre toujours ses 5 chemins : l'ancien defaut
        # ecrit en toutes lettres n'est pas un choix de l'utilisateur.
        config = parse_waf_config({
            "blocklist": {"path": "secure/waf/blocklist.json"},
            "magnet": {"paths": {"blocklist_file": "secure/waf/magnet-blocklist.txt"}},
        })
        self.assertEqual(config.blocklist.path, "var/lib/waf/blocklist.json")
        self.assertEqual(config.magnet.paths.blocklist_file, "var/lib/waf/magnet-blocklist.txt")

    def test_custom_blocklist_paths_are_kept(self):
        config = parse_waf_config({
            "blocklist": {"path": "secure/waf/ma-liste.json"},
            "magnet": {"paths": {"blocklist_file": "/etc/blocklist.txt"}},
        })
        self.assertEqual(config.blocklist.path, "secure/waf/ma-liste.json")
        self.assertEqual(config.magnet.paths.blocklist_file, "/etc/blocklist.txt")

    def test_magnet_paths_overridable(self):
        settings = {"magnet": {"enabled": True, "script": "secure/waf/scripts/waf.lua", "paths": {
            "blocklist_file": "custom/blocklist.txt",
        }}}
        config = parse_waf_config(settings)
        self.assertEqual(config.magnet.paths.blocklist_file, "custom/blocklist.txt")
        # Les 4 autres gardent leur defaut, non ecrases par un override partiel.
        self.assertEqual(config.magnet.paths.alerts_log, "var/log/waf-magnet-alerts.log")


class TestValidateWafConfig(unittest.TestCase):
    def test_valid_config_with_rule_paths_passes(self):
        config = parse_waf_config({"rules": {"paths": ["secure/waf/rules/core.json"]}})
        self.assertEqual(validate_waf_config(config), [])

    def test_empty_rule_paths_rejected(self):
        config = parse_waf_config({})
        errors = validate_waf_config(config)
        self.assertTrue(any("rules.paths" in e for e in errors))

    def test_keyword_lists_alone_satisfies_non_empty_rules_requirement(self):
        config = parse_waf_config({
            "rules": {"keyword_lists": [{"id": "X", "scope": ["referer"], "file": "secure/waf/rules/keywords/x.txt"}]},
        })
        errors = validate_waf_config(config)
        self.assertEqual(errors, [])

    def test_invalid_keyword_list_definition_rejected(self):
        config = parse_waf_config({
            "rules": {
                "paths": ["secure/waf/rules/core.json"],
                "keyword_lists": [{"id": "X", "scope": ["cookies"], "file": "x.txt"}],
            },
        })
        errors = validate_waf_config(config)
        self.assertTrue(any("scope inconnu" in e for e in errors))

    def test_invalid_mode_rejected(self):
        config = WafConfig(mode="allow-all")  # type: ignore[arg-type]
        errors = validate_waf_config(config)
        self.assertTrue(any("mode" in e for e in errors))

    def test_zero_block_threshold_rejected(self):
        config = parse_waf_config({"rules": {"paths": ["x"]}, "scoring": {"block_threshold": 0}})
        errors = validate_waf_config(config)
        self.assertTrue(any("block_threshold" in e for e in errors))


class TestNeverAutoBlockConfig(unittest.TestCase):
    """OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.13."""
    def test_default_networks_applied(self):
        config = parse_waf_config({})
        self.assertIn("127.0.0.0/8", config.reputation.never_auto_block)
        self.assertIn("100.64.0.0/10", config.reputation.never_auto_block)
        self.assertNotIn("100.0.0.0/8", config.reputation.never_auto_block)

    def test_override(self):
        config = parse_waf_config({"reputation": {"never_auto_block": ["10.0.0.0/8"]}})
        self.assertEqual(config.reputation.never_auto_block, ("10.0.0.0/8",))

    def test_invalid_network_rejected(self):
        config = parse_waf_config({
            "rules": {"paths": ["secure/waf/rules/core.json"]},
            "reputation": {"never_auto_block": ["10.0.0.0/8", "pas-un-reseau"]},
        })
        errors = validate_waf_config(config)
        self.assertTrue(any("never_auto_block" in e and "pas-un-reseau" in e for e in errors))


class TestReputationEnabledOnListLoad(unittest.TestCase):
    """Lot 2.2 : defauts du code inchanges, activation au chargement d'une liste."""
    def test_code_defaults_unchanged(self):
        config = parse_waf_config({})
        self.assertFalse(config.reputation.enabled)
        self.assertFalse(config.reputation.auto_block)

    def test_enables_both_when_absent(self):
        settings, changes = with_reputation_enabled_for_lists({"mode": "block"})
        self.assertEqual(len(changes), 2)
        self.assertTrue(settings["reputation"]["enabled"])
        self.assertTrue(settings["reputation"]["auto_block"])
        self.assertEqual(settings["mode"], "block")

    def test_keeps_other_reputation_settings_and_does_not_mutate_input(self):
        original = {"reputation": {"enabled": True, "suspicious_threshold": 7}}
        settings, changes = with_reputation_enabled_for_lists(original)
        self.assertEqual(changes, ("auto-ban active (blocklist temporaire, reponse 451)",))
        self.assertEqual(settings["reputation"]["suspicious_threshold"], 7)
        self.assertNotIn("auto_block", original["reputation"])

    def test_nothing_to_do_when_already_enabled(self):
        original = {"reputation": {"enabled": True, "auto_block": True}}
        settings, changes = with_reputation_enabled_for_lists(original)
        self.assertEqual(changes, ())
        self.assertIs(settings, original)


if __name__ == "__main__":
    unittest.main()
