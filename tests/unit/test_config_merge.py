# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.config.merge import compute_merged_config, deep_merge
from omega_serv.domain.config.option import Option
from omega_serv.domain.config.profile import Profile


class TestDeepMerge(unittest.TestCase):
    def test_flat_override(self):
        result = deep_merge({"a": 1, "b": 2}, {"b": 3})
        self.assertEqual(result, {"a": 1, "b": 3})

    def test_nested_dicts_merge_recursively(self):
        base = {"server": {"bind": "127.0.0.1", "port": 8080}}
        overlay = {"server": {"port": 9090}}
        result = deep_merge(base, overlay)
        self.assertEqual(result, {"server": {"bind": "127.0.0.1", "port": 9090}})

    def test_list_in_overlay_replaces_entirely(self):
        base = {"methods": ["GET", "HEAD"]}
        overlay = {"methods": ["GET"]}
        result = deep_merge(base, overlay)
        self.assertEqual(result["methods"], ["GET"])

    def test_does_not_mutate_inputs(self):
        base = {"a": {"x": 1}}
        overlay = {"a": {"y": 2}}
        deep_merge(base, overlay)
        self.assertEqual(base, {"a": {"x": 1}})
        self.assertEqual(overlay, {"a": {"y": 2}})


class TestComputeMergedConfig(unittest.TestCase):
    def test_profile_values_are_applied(self):
        profile = Profile(name="hardened", description="", values={"server": {"bind": "0.0.0.0"}})
        config = compute_merged_config(profile, options_to_keep={})
        self.assertEqual(config.profile, "hardened")
        self.assertEqual(config.server.bind, "0.0.0.0")

    def test_kept_options_are_reapplied_after_profile(self):
        profile = Profile(name="hardened", description="", values={"options": {"waf": {"enabled": False}}})
        kept = {"waf": Option(name="waf", enabled=True, settings={"mode": "log-only"})}
        config = compute_merged_config(profile, options_to_keep=kept)
        self.assertTrue(config.option_enabled("waf"))
        self.assertEqual(config.options["waf"].settings["mode"], "log-only")

    def test_user_overlay_applied_last(self):
        profile = Profile(name="standard", description="", values={"server": {"bind": "0.0.0.0"}})
        config = compute_merged_config(profile, options_to_keep={}, user_overlay={"server": {"bind": "10.0.0.1"}})
        self.assertEqual(config.server.bind, "10.0.0.1")

    def test_no_options_to_keep_uses_profile_defaults(self):
        profile = Profile(name="minimal", description="", values={})
        config = compute_merged_config(profile, options_to_keep={})
        self.assertFalse(config.option_enabled("waf"))


if __name__ == "__main__":
    unittest.main()
