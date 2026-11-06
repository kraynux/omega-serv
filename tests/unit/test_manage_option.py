import tempfile
import unittest
from pathlib import Path

from omega_serv.application.config.manage_option import set_option_enabled, waf_rule_packs_present
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestSetOptionEnabled(unittest.TestCase):
    def test_enable_unknown_option_fails(self):
        result = set_option_enabled(OmegaServConfig(), "cgi", True)
        self.assertFalse(result.success)
        self.assertIsNone(result.new_config)

    def test_enable_known_option(self):
        result = set_option_enabled(OmegaServConfig(), "waf", True)
        self.assertTrue(result.success)
        self.assertTrue(result.new_config.option_enabled("waf"))

    def test_disable_preserves_existing_settings(self):
        current = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True, "mode": "block"}}})
        result = set_option_enabled(current, "waf", False)
        self.assertTrue(result.success)
        self.assertFalse(result.new_config.option_enabled("waf"))
        self.assertEqual(result.new_config.options["waf"].settings["mode"], "block")

    def test_other_options_are_untouched(self):
        current = OmegaServConfig.from_dict({"options": {"cache": {"enabled": True}}})
        result = set_option_enabled(current, "waf", True)
        self.assertTrue(result.new_config.option_enabled("cache"))
        self.assertTrue(result.new_config.option_enabled("waf"))


PACKS = ("secure/waf/rules/body-sqli.json", "secure/waf/rules/body-xss.json")


class TestFirstWafActivation(unittest.TestCase):
    """Premiere activation du WAF sans pack : sans regles, la configuration serait refusee au demarrage."""

    def test_first_activation_adds_present_packs_and_stays_log_only(self):
        result = set_option_enabled(OmegaServConfig(), "waf", True, PACKS)
        settings = result.new_config.options["waf"].settings
        self.assertEqual(settings["rules"]["paths"], list(PACKS))
        self.assertNotIn("mode", settings)  # log-only par defaut : jamais de blocage decide ici
        self.assertIn("2 pack(s)", result.message)
        self.assertIn("log-only", result.message)

    def test_existing_packs_are_never_replaced(self):
        current = OmegaServConfig.from_dict({"options": {"waf": {
            "enabled": False, "rules": {"paths": ["secure/waf/rules/custom.json"]}}}})
        result = set_option_enabled(current, "waf", True, PACKS)
        self.assertEqual(result.new_config.options["waf"].settings["rules"]["paths"], ["secure/waf/rules/custom.json"])
        self.assertNotIn("pack", result.message)

    def test_keyword_lists_alone_count_as_a_choice(self):
        current = OmegaServConfig.from_dict({"options": {"waf": {"enabled": False, "rules": {"keyword_lists": [
            {"id": "k", "label": "k", "file": "secure/waf/rules/keywords/k.txt", "scope": ["path"]}]}}}})
        result = set_option_enabled(current, "waf", True, PACKS)
        self.assertNotIn("paths", result.new_config.options["waf"].settings["rules"])

    def test_disabling_or_other_options_add_nothing(self):
        self.assertNotIn("rules", set_option_enabled(OmegaServConfig(), "waf", False, PACKS).new_config.options["waf"].settings)
        self.assertNotIn("rules", set_option_enabled(OmegaServConfig(), "cache", True, PACKS).new_config.options["cache"].settings)

    def test_block_mode_is_announced(self):
        current = OmegaServConfig.from_dict({"options": {"waf": {"enabled": False, "mode": "block"}}})
        message = set_option_enabled(current, "waf", True, PACKS).message
        self.assertIn("Mode block.", message)

    def test_packs_present_lists_real_json_files_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rules = root / "secure" / "waf" / "rules"
            (rules / "keywords").mkdir(parents=True)
            for name in ("b.json", "a.json", "notes.txt"):
                (rules / name).write_text("{}")
            self.assertEqual(waf_rule_packs_present(LocalFilesystem(), root),
                             ("secure/waf/rules/a.json", "secure/waf/rules/b.json"))
            self.assertEqual(waf_rule_packs_present(LocalFilesystem(), root / "absent"), ())


if __name__ == "__main__":
    unittest.main()
