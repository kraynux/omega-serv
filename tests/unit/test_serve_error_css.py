"""Meme principe que test_serve_icon.py : le CSS des pages d'erreur par
defaut est servi en chemin reserve (`ERROR_CSS_URL_PREFIX`), jamais via
une lecture disque - verifie ici que seul le nom de fichier attendu est
servi (pas de traversee de chemin possible, contenu 100% statique)."""
import unittest

from omega_serv.application.server.serve_error_css import (
    ERROR_CSS_URL_PREFIX,
    handle_error_css_request,
)
from omega_serv.domain.http.error_pages import error_pages_css
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus


def _make_request(method: str, filename: str) -> HttpRequest:
    path = ERROR_CSS_URL_PREFIX + filename
    return HttpRequest(
        request_id="test-id",
        remote_ip="203.0.113.10",
        peer_ip="203.0.113.10",
        method=method,
        path=path,
        raw_path=path,
        query="",
        headers=HttpHeaders.from_pairs([]),
        body=None,
        content_length=None,
        is_tls=False,
    )


class TestHandleErrorCssRequest(unittest.TestCase):
    def test_known_filename_returns_ok_with_css_content_type(self):
        response = handle_error_css_request(_make_request("GET", "error-pages.css"))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.headers["Content-Type"], "text/css; charset=utf-8")

    def test_body_matches_error_pages_css(self):
        response = handle_error_css_request(_make_request("GET", "error-pages.css"))
        self.assertEqual(response.body, error_pages_css().encode("utf-8"))

    def test_head_returns_headers_without_body(self):
        response = handle_error_css_request(_make_request("HEAD", "error-pages.css"))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"")
        self.assertIn("Content-Length", response.headers)

    def test_unknown_filename_returns_not_found(self):
        response = handle_error_css_request(_make_request("GET", "autre.css"))
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_path_traversal_attempt_returns_not_found(self):
        response = handle_error_css_request(_make_request("GET", "../secret.css"))
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_unsupported_method_returns_method_not_allowed(self):
        response = handle_error_css_request(_make_request("POST", "error-pages.css"))
        self.assertEqual(response.status, HttpStatus.METHOD_NOT_ALLOWED)
        self.assertIn("Allow", response.headers)

    def test_response_is_cacheable(self):
        response = handle_error_css_request(_make_request("GET", "error-pages.css"))
        self.assertIn("Cache-Control", response.headers)


if __name__ == "__main__":
    unittest.main()
