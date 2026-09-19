import unittest

from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.security.path_policy import PathRejectionReason, normalize_uri_path


class TestNormalizeUriPath(unittest.TestCase):
    def test_simple_valid_path(self):
        decision = normalize_uri_path("/public/index.html")
        self.assertTrue(decision.ok)
        self.assertEqual(decision.segments, ("public", "index.html"))

    def test_empty_path_rejected(self):
        decision = normalize_uri_path("")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.rejection_reason, PathRejectionReason.EMPTY_PATH)

    def test_leading_traversal_rejected(self):
        decision = normalize_uri_path("/../etc/passwd")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.rejection_reason, PathRejectionReason.TRAVERSAL_ATTEMPT)
        self.assertEqual(decision.suggested_status, HttpStatus.FORBIDDEN)

    def test_internal_traversal_that_stays_within_bounds_is_safe(self):
        decision = normalize_uri_path("/a/b/../c")
        self.assertTrue(decision.ok)
        self.assertEqual(decision.segments, ("a", "c"))

    def test_nul_byte_rejected(self):
        decision = normalize_uri_path("/index.html\x00.php")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.rejection_reason, PathRejectionReason.NUL_BYTE)

    def test_control_character_rejected(self):
        decision = normalize_uri_path("/index.html\r\nInjected: true")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.rejection_reason, PathRejectionReason.CONTROL_CHARACTER)

    def test_percent_encoded_traversal_rejected(self):
        decision = normalize_uri_path("/%2e%2e/%2e%2e/etc/passwd")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.rejection_reason, PathRejectionReason.TRAVERSAL_ATTEMPT)

    def test_double_encoded_nul_byte_rejected(self):
        decision = normalize_uri_path("/index.html%2500.php")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.rejection_reason, PathRejectionReason.NUL_BYTE)

    def test_dot_segments_are_collapsed(self):
        decision = normalize_uri_path("/./public/./index.html")
        self.assertTrue(decision.ok)
        self.assertEqual(decision.segments, ("public", "index.html"))

    def test_backslash_treated_as_separator(self):
        decision = normalize_uri_path("/public\\..\\..\\etc\\passwd")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.rejection_reason, PathRejectionReason.TRAVERSAL_ATTEMPT)


if __name__ == "__main__":
    unittest.main()
