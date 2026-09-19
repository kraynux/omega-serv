import unittest

from omega_serv.domain.routing.alias import AliasRule, parse_alias_rules, validate_alias_rule


class TestParseAliasRules(unittest.TestCase):
    def test_parses_list(self):
        rules = parse_alias_rules([
            {"url_prefix": "/downloads/", "target_path": "webroot/public/downloads/"},
        ])
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].url_prefix, "/downloads/")
        self.assertFalse(rules[0].allow_outside_webroot)


class TestValidateAliasRule(unittest.TestCase):
    def test_valid_rule_inside_webroot(self):
        rule = AliasRule(url_prefix="/downloads/", target_path="webroot/public/downloads/")
        self.assertIsNone(validate_alias_rule(rule))

    def test_url_prefix_must_start_with_slash(self):
        rule = AliasRule(url_prefix="downloads/", target_path="webroot/public/")
        self.assertIsNotNone(validate_alias_rule(rule))

    def test_target_outside_webroot_without_flag_rejected(self):
        rule = AliasRule(url_prefix="/x/", target_path="somewhere/else/")
        self.assertIsNotNone(validate_alias_rule(rule))

    def test_target_outside_webroot_with_flag_allowed(self):
        rule = AliasRule(url_prefix="/x/", target_path="somewhere/else/", allow_outside_webroot=True)
        self.assertIsNone(validate_alias_rule(rule))

    def test_target_secure_always_rejected_even_with_flag(self):
        rule = AliasRule(url_prefix="/x/", target_path="secure/auth/", allow_outside_webroot=True)
        self.assertIsNotNone(validate_alias_rule(rule))

    def test_target_config_always_rejected(self):
        rule = AliasRule(url_prefix="/x/", target_path="config/", allow_outside_webroot=True)
        self.assertIsNotNone(validate_alias_rule(rule))

    def test_target_var_always_rejected(self):
        rule = AliasRule(url_prefix="/x/", target_path="var/log/", allow_outside_webroot=True)
        self.assertIsNotNone(validate_alias_rule(rule))


if __name__ == "__main__":
    unittest.main()
