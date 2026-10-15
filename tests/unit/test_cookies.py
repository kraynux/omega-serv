import unittest

from omega_serv.domain.http.cookies import build_set_cookie_header, parse_cookie_header


class TestParseCookieHeader(unittest.TestCase):
    def test_none_returns_empty_dict(self):
        self.assertEqual(parse_cookie_header(None), {})

    def test_empty_string_returns_empty_dict(self):
        self.assertEqual(parse_cookie_header(""), {})

    def test_single_cookie(self):
        self.assertEqual(parse_cookie_header("session=abc123"), {"session": "abc123"})

    def test_multiple_cookies(self):
        self.assertEqual(
            parse_cookie_header("a=1; b=2; c=3"),
            {"a": "1", "b": "2", "c": "3"},
        )

    def test_malformed_chunk_without_equals_is_ignored(self):
        self.assertEqual(parse_cookie_header("a=1; malformed; b=2"), {"a": "1", "b": "2"})

    def test_value_can_contain_equals_sign(self):
        self.assertEqual(parse_cookie_header("token=abc=def"), {"token": "abc=def"})

    def test_whitespace_around_chunks_is_trimmed(self):
        self.assertEqual(parse_cookie_header("  a=1 ;  b=2  "), {"a": "1", "b": "2"})


class TestBuildSetCookieHeader(unittest.TestCase):
    def test_contains_name_and_value(self):
        header = build_set_cookie_header("sticky", "abc123", max_age_seconds=60)
        self.assertIn("sticky=abc123", header)

    def test_always_includes_secure_and_http_only(self):
        header = build_set_cookie_header("sticky", "abc123", max_age_seconds=60)
        self.assertIn("Secure", header)
        self.assertIn("HttpOnly", header)

    def test_includes_max_age_path_and_same_site(self):
        header = build_set_cookie_header("sticky", "abc123", max_age_seconds=3600)
        self.assertIn("Max-Age=3600", header)
        self.assertIn("Path=/", header)
        self.assertIn("SameSite=Lax", header)


if __name__ == "__main__":
    unittest.main()
