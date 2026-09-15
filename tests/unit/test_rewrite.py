# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.routing.rewrite import RewriteRule, apply_rewrites, parse_rewrite_rules


class TestApplyRewrites(unittest.TestCase):
    def test_no_matching_rule_returns_original(self):
        result = apply_rewrites("/foo", [RewriteRule("/bar", "/baz")])
        self.assertEqual(result.final_path, "/foo")
        self.assertFalse(result.loop_detected)

    def test_single_rewrite_applies(self):
        result = apply_rewrites("/old/page", [RewriteRule("/old", "/new")])
        self.assertEqual(result.final_path, "/new/page")
        self.assertFalse(result.loop_detected)

    def test_chained_rewrites_apply_in_sequence(self):
        rules = [RewriteRule("/a", "/b"), RewriteRule("/b", "/c")]
        result = apply_rewrites("/a/x", rules)
        self.assertEqual(result.final_path, "/c/x")
        self.assertFalse(result.loop_detected)

    def test_direct_loop_is_detected(self):
        rules = [RewriteRule("/a", "/b"), RewriteRule("/b", "/a")]
        result = apply_rewrites("/a", rules)
        self.assertTrue(result.loop_detected)
        self.assertEqual(result.final_path, "/a")  # chemin original renvoye, jamais un etat intermediaire

    def test_self_rewrite_is_detected_as_loop(self):
        result = apply_rewrites("/a", [RewriteRule("/a", "/a")])
        self.assertTrue(result.loop_detected)

    def test_parse_rewrite_rules(self):
        rules = parse_rewrite_rules([{"match_prefix": "/x", "replacement_prefix": "/y"}])
        self.assertEqual(rules[0].match_prefix, "/x")


if __name__ == "__main__":
    unittest.main()
