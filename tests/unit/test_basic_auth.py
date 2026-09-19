import base64
import unittest

from omega_serv.domain.security.auth.basic_auth import (
    build_www_authenticate_header,
    parse_basic_auth_header,
)


def _basic_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


class TestParseBasicAuthHeader(unittest.TestCase):
    def test_valid_header_parses(self):
        result = parse_basic_auth_header(_basic_header("admin", "hunter2"))
        self.assertEqual(result, ("admin", "hunter2"))

    def test_password_containing_colon_preserved(self):
        result = parse_basic_auth_header(_basic_header("admin", "pass:word"))
        self.assertEqual(result, ("admin", "pass:word"))

    def test_none_header_returns_none(self):
        self.assertIsNone(parse_basic_auth_header(None))

    def test_non_basic_scheme_returns_none(self):
        self.assertIsNone(parse_basic_auth_header("Bearer sometoken"))

    def test_invalid_base64_returns_none(self):
        self.assertIsNone(parse_basic_auth_header("Basic not-valid-base64!!!"))

    def test_missing_colon_returns_none(self):
        token = base64.b64encode(b"no-colon-here").decode("ascii")
        self.assertIsNone(parse_basic_auth_header(f"Basic {token}"))

    def test_non_utf8_bytes_returns_none(self):
        token = base64.b64encode(b"\xff\xfe:invalid").decode("ascii")
        self.assertIsNone(parse_basic_auth_header(f"Basic {token}"))

    def test_empty_string_header_returns_none(self):
        self.assertIsNone(parse_basic_auth_header(""))


class TestBuildWwwAuthenticateHeader(unittest.TestCase):
    def test_includes_realm(self):
        self.assertEqual(build_www_authenticate_header("Zone privee"), 'Basic realm="Zone privee"')


if __name__ == "__main__":
    unittest.main()
