"""Helpers partages des ecrans WAF (interfaces/tui/screens/_waf_rule_paths.py)."""
import unittest

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.interfaces.tui.screens._waf_rule_paths import (
    get_waf_rule_paths,
    with_waf_rule_paths,
)


class TestWithWafRulePaths(unittest.TestCase):
    def test_keyword_lists_are_preserved(self):
        """Bug du 2026-10-18 : ajouter une regle custom effacait les keyword_lists."""
        lists = [{"id": "sensitive-paths-hostile", "scope": ["path"], "file": "f.txt", "match": "path"}]
        config = OmegaServConfig.from_dict({"options": {"waf": {
            "enabled": True, "rules": {"paths": ["a.json"], "keyword_lists": lists},
        }}})
        updated = with_waf_rule_paths(config, ["a.json", "secure/waf/rules/custom.json"])
        rules = updated.options["waf"].settings["rules"]
        self.assertEqual(rules["keyword_lists"], lists)
        self.assertEqual(get_waf_rule_paths(updated), ["a.json", "secure/waf/rules/custom.json"])
        self.assertTrue(updated.options["waf"].enabled)

    def test_creates_waf_option_when_absent(self):
        updated = with_waf_rule_paths(OmegaServConfig.from_dict({}), ["a.json"])
        self.assertEqual(updated.options["waf"].settings["rules"], {"paths": ["a.json"]})
        self.assertFalse(updated.options["waf"].enabled)


if __name__ == "__main__":
    unittest.main()
