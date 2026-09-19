"""Meme securite que recommandee (retour utilisateur, citation OWASP) :
verifie ici que seul un nom d'icone CONNU A L'AVANCE (`ICON_FILENAMES`)
peut jamais etre servi - jamais une resolution de chemin sur ce que le
client demande, donc aucune traversee de repertoire possible meme si le
nom contient "..", un chemin absolu, ou un chemin vers un fichier reel
mais hors du repertoire d'icones."""
import unittest

from omega_serv.application.server.serve_icon import ICON_URL_PREFIX, handle_icon_request
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.icon_registry import DIRECTORY_ICON
from omega_serv.infrastructure.icons.icon_files import read_icon_svg


def _make_request(method: str, name: str) -> HttpRequest:
    path = ICON_URL_PREFIX + name
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


class TestHandleIconRequest(unittest.TestCase):
    def test_known_icon_returns_ok_with_svg_content_type(self):
        response = handle_icon_request(_make_request("GET", DIRECTORY_ICON))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.headers["Content-Type"], "image/svg+xml")

    def test_known_icon_body_matches_the_file_on_disk(self):
        response = handle_icon_request(_make_request("GET", DIRECTORY_ICON))
        self.assertEqual(response.body, read_icon_svg(DIRECTORY_ICON))

    def test_head_returns_headers_without_body(self):
        response = handle_icon_request(_make_request("HEAD", DIRECTORY_ICON))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"")
        self.assertIn("Content-Length", response.headers)

    def test_response_is_cacheable(self):
        response = handle_icon_request(_make_request("GET", DIRECTORY_ICON))
        self.assertIn("max-age", response.headers["Cache-Control"])

    def test_post_not_allowed(self):
        response = handle_icon_request(_make_request("POST", DIRECTORY_ICON))
        self.assertEqual(response.status, HttpStatus.METHOD_NOT_ALLOWED)

    def test_unknown_name_is_404(self):
        response = handle_icon_request(_make_request("GET", "totally-not-a-real-icon.svg"))
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_directory_traversal_attempt_is_404_not_a_file_leak(self):
        response = handle_icon_request(_make_request("GET", "../../../../etc/passwd"))
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_absolute_path_attempt_is_404(self):
        response = handle_icon_request(_make_request("GET", "/etc/passwd"))
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_empty_name_is_404(self):
        response = handle_icon_request(_make_request("GET", ""))
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
