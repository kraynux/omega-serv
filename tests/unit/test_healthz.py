import unittest

from omega_serv.application.server.healthz import handle_healthz
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus


def _make_request(method: str) -> HttpRequest:
    return HttpRequest(
        request_id="test-id",
        remote_ip="203.0.113.10",
        peer_ip="203.0.113.10",
        method=method,
        path="/healthz",
        raw_path="/healthz",
        query="",
        headers=HttpHeaders.from_pairs([]),
        body=None,
        content_length=None,
        is_tls=False,
    )


class TestHealthz(unittest.TestCase):
    def test_get_returns_ok_with_body(self):
        response = handle_healthz(_make_request("GET"))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"OK")

    def test_head_returns_ok_without_body(self):
        response = handle_healthz(_make_request("HEAD"))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"")
        self.assertEqual(response.headers["Content-Length"], "2")

    def test_post_not_allowed(self):
        response = handle_healthz(_make_request("POST"))
        self.assertEqual(response.status, HttpStatus.METHOD_NOT_ALLOWED)

    def test_no_sensitive_info_leaked(self):
        response = handle_healthz(_make_request("GET"))
        self.assertEqual(response.body, b"OK")
        self.assertNotIn("Server", response.headers)


if __name__ == "__main__":
    unittest.main()
