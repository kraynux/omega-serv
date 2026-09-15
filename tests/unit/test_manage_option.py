# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.application.config.manage_option import set_option_enabled
from omega_serv.domain.config.entities import OmegaServConfig


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


if __name__ == "__main__":
    unittest.main()
