# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.rules import detect_conflicts, has_blocking_conflicts


class TestDetectConflicts(unittest.TestCase):
    def test_default_config_has_no_conflicts(self):
        self.assertEqual(detect_conflicts(OmegaServConfig()), [])

    def test_trusted_proxy_without_networks_is_a_conflict(self):
        config = OmegaServConfig.from_dict({"options": {"trusted_proxy": {"enabled": True}}})
        conflicts = detect_conflicts(config)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].severity, "error")

    def test_trusted_proxy_with_networks_is_fine(self):
        config = OmegaServConfig.from_dict({
            "options": {"trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"]}},
        })
        self.assertEqual(detect_conflicts(config), [])

    def test_trusted_proxy_disabled_is_never_a_conflict(self):
        config = OmegaServConfig.from_dict({"options": {"trusted_proxy": {"enabled": False}}})
        self.assertEqual(detect_conflicts(config), [])


class TestHasBlockingConflicts(unittest.TestCase):
    def test_empty_list_is_not_blocking(self):
        self.assertFalse(has_blocking_conflicts([]))

    def test_error_severity_is_blocking(self):
        config = OmegaServConfig.from_dict({"options": {"trusted_proxy": {"enabled": True}}})
        self.assertTrue(has_blocking_conflicts(detect_conflicts(config)))


if __name__ == "__main__":
    unittest.main()
