import unittest

from omega_serv.domain.routing.redirect import (
    RedirectRule,
    parse_redirect_rules,
    validate_redirect_rule,
)


class TestParseRedirectRules(unittest.TestCase):
    def test_parses_with_default_status(self):
        rules = parse_redirect_rules([{"url_prefix": "/old/", "destination": "/new/"}])
        self.assertEqual(rules[0].status_code, 302)

    def test_parses_explicit_status(self):
        rules = parse_redirect_rules([{"url_prefix": "/old/", "destination": "/new/", "status_code": 301}])
        self.assertEqual(rules[0].status_code, 301)


class TestValidateRedirectRule(unittest.TestCase):
    def test_valid_rule(self):
        rule = RedirectRule(url_prefix="/old/", destination="/new/", status_code=301)
        self.assertIsNone(validate_redirect_rule(rule))

    def test_invalid_status_code_rejected(self):
        rule = RedirectRule(url_prefix="/old/", destination="/new/", status_code=200)
        self.assertIsNotNone(validate_redirect_rule(rule))

    def test_empty_destination_rejected(self):
        rule = RedirectRule(url_prefix="/old/", destination="", status_code=301)
        self.assertIsNotNone(validate_redirect_rule(rule))

    def test_url_prefix_must_start_with_slash(self):
        rule = RedirectRule(url_prefix="old/", destination="/new/", status_code=301)
        self.assertIsNotNone(validate_redirect_rule(rule))


if __name__ == "__main__":
    unittest.main()
