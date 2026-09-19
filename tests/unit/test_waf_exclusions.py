import unittest

from omega_serv.domain.security.waf.exclusions import is_extension_excluded, matches_any_prefix


class TestMatchesAnyPrefix(unittest.TestCase):
    def test_matches_configured_prefix(self):
        self.assertTrue(matches_any_prefix("/healthz", ("/healthz",)))

    def test_no_match_returns_false(self):
        self.assertFalse(matches_any_prefix("/index.html", ("/healthz",)))

    def test_empty_prefixes_never_matches(self):
        self.assertFalse(matches_any_prefix("/healthz", ()))


class TestIsExtensionExcluded(unittest.TestCase):
    def test_matches_case_insensitively(self):
        self.assertTrue(is_extension_excluded("/style.CSS", (".css",)))

    def test_no_match(self):
        self.assertFalse(is_extension_excluded("/index.html", (".css", ".js")))


if __name__ == "__main__":
    unittest.main()
