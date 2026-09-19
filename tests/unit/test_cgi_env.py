import unittest

from omega_serv.domain.http.cgi_env import build_cgi_env
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest


def _request(method="GET", query="", headers=None, body=None, is_tls=False) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method=method,
        path="/app/index.php", raw_path="/app/index.php" + (f"?{query}" if query else ""), query=query,
        headers=HttpHeaders.from_pairs(headers or []), body=body, content_length=None, is_tls=is_tls,
    )


class TestBuildCgiEnv(unittest.TestCase):
    def test_basic_fields(self):
        env = build_cgi_env(_request(), "/srv/app/index.php", "/app/index.php", "/srv/app", "localhost", 8080)
        self.assertEqual(env["REQUEST_METHOD"], "GET")
        self.assertEqual(env["SCRIPT_FILENAME"], "/srv/app/index.php")
        self.assertEqual(env["SERVER_NAME"], "localhost")
        self.assertEqual(env["SERVER_PORT"], "8080")
        self.assertEqual(env["REDIRECT_STATUS"], "200")
        self.assertEqual(env["GATEWAY_INTERFACE"], "CGI/1.1")

    def test_query_string_forwarded(self):
        env = build_cgi_env(_request(query="q=1"), "/x", "/x", "/srv", "h", 80)
        self.assertEqual(env["QUERY_STRING"], "q=1")

    def test_https_set_when_tls(self):
        env = build_cgi_env(_request(is_tls=True), "/x", "/x", "/srv", "h", 443)
        self.assertEqual(env["HTTPS"], "on")

    def test_https_absent_without_tls(self):
        env = build_cgi_env(_request(is_tls=False), "/x", "/x", "/srv", "h", 80)
        self.assertNotIn("HTTPS", env)

    def test_content_type_and_length_forwarded(self):
        env = build_cgi_env(
            _request(method="POST", headers=[("Content-Type", "application/json")], body=b'{"a":1}'),
            "/x", "/x", "/srv", "h", 80,
        )
        self.assertEqual(env["CONTENT_TYPE"], "application/json")
        self.assertEqual(env["CONTENT_LENGTH"], "7")

    def test_no_body_means_no_content_length(self):
        env = build_cgi_env(_request(), "/x", "/x", "/srv", "h", 80)
        self.assertNotIn("CONTENT_LENGTH", env)

    def test_headers_forwarded_as_http_prefixed(self):
        env = build_cgi_env(_request(headers=[("User-Agent", "curl/8.0"), ("X-Custom-Header", "value")]), "/x", "/x", "/srv", "h", 80)
        self.assertEqual(env["HTTP_USER_AGENT"], "curl/8.0")
        self.assertEqual(env["HTTP_X_CUSTOM_HEADER"], "value")

    def test_content_type_header_not_duplicated_as_http_prefixed(self):
        env = build_cgi_env(_request(headers=[("Content-Type", "text/plain")]), "/x", "/x", "/srv", "h", 80)
        self.assertNotIn("HTTP_CONTENT_TYPE", env)


if __name__ == "__main__":
    unittest.main()
