import unittest

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.security.access_policy import (
    is_denied_path,
    is_method_allowed,
    validate_host_header,
)


class TestIsMethodAllowed(unittest.TestCase):
    def test_default_allows_get_and_head(self):
        security = SecurityConfig()
        self.assertTrue(is_method_allowed("GET", security))
        self.assertTrue(is_method_allowed("HEAD", security))

    def test_default_rejects_post(self):
        security = SecurityConfig()
        self.assertFalse(is_method_allowed("POST", security))

    def test_rejects_trace_track_connect_by_default(self):
        security = SecurityConfig()
        for method in ("TRACE", "TRACK", "CONNECT", "DELETE"):
            self.assertFalse(is_method_allowed(method, security), method)

    def test_explicit_allowlist_permits_post(self):
        security = SecurityConfig(allowed_methods=("GET", "HEAD", "POST"))
        self.assertTrue(is_method_allowed("POST", security))


class TestValidateHostHeader(unittest.TestCase):
    def test_valid_single_host_is_ok(self):
        self.assertIsNone(validate_host_header((("Host", "example.com"),)))

    def test_missing_host_is_rejected(self):
        self.assertIsNotNone(validate_host_header((("User-Agent", "x"),)))

    def test_empty_host_is_rejected(self):
        self.assertIsNotNone(validate_host_header((("Host", ""),)))

    def test_duplicate_host_is_rejected(self):
        reason = validate_host_header((("Host", "a.com"), ("Host", "b.com")))
        self.assertIsNotNone(reason)

    def test_duplicate_identical_host_is_still_rejected(self):
        reason = validate_host_header((("Host", "a.com"), ("Host", "a.com")))
        self.assertIsNotNone(reason)

    def test_host_with_control_character_is_rejected(self):
        reason = validate_host_header((("Host", "example.com\r\nInjected: 1"),))
        self.assertIsNotNone(reason)


class TestIsDeniedPath(unittest.TestCase):
    def test_normal_path_is_allowed(self):
        self.assertFalse(is_denied_path(("public", "index.html"), SecurityConfig()))

    def test_dotfile_is_denied(self):
        self.assertTrue(is_denied_path((".env",), SecurityConfig()))

    def test_sensitive_extension_is_denied(self):
        self.assertTrue(is_denied_path(("backup.sql",), SecurityConfig()))

    def test_deny_pattern_is_denied(self):
        self.assertTrue(is_denied_path((".htpasswd",), SecurityConfig()))

    def test_empty_segments_is_allowed(self):
        self.assertFalse(is_denied_path((), SecurityConfig()))


if __name__ == "__main__":
    unittest.main()
