# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.http.headers import HttpHeaders, has_control_characters, total_size_bytes
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus


class TestHttpHeaders(unittest.TestCase):
    def test_case_insensitive_lookup(self):
        headers = HttpHeaders.from_pairs([("Content-Type", "text/html")])
        self.assertEqual(headers.get("content-type"), "text/html")
        self.assertEqual(headers.get("CONTENT-TYPE"), "text/html")
        self.assertIn("Content-Type", headers)

    def test_missing_header_returns_default(self):
        headers = HttpHeaders.from_pairs([])
        self.assertIsNone(headers.get("x-absent"))
        self.assertEqual(headers.get("x-absent", "fallback"), "fallback")

    def test_has_control_characters_detects_crlf(self):
        self.assertTrue(has_control_characters("value\r\nInjected: true"))
        self.assertFalse(has_control_characters("normal value"))

    def test_total_size_bytes(self):
        pairs = [("Host", "example.com")]
        # "Host" (4) + "example.com" (11) + 4 (": " + CRLF) = 19
        self.assertEqual(total_size_bytes(pairs), 19)


class TestHttpRequest(unittest.TestCase):
    def test_header_accessor(self):
        request = HttpRequest(
            request_id="r1",
            remote_ip="203.0.113.10",
            peer_ip="203.0.113.10",
            method="GET",
            path="/index.html",
            raw_path="/index.html",
            query="",
            headers=HttpHeaders.from_pairs([("User-Agent", "test")]),
            body=None,
            content_length=None,
            is_tls=False,
        )
        self.assertEqual(request.header("user-agent"), "test")
        self.assertIsNone(request.header("x-absent"))


class TestHttpResponse(unittest.TestCase):
    def test_force_security_header_overrides(self):
        response = HttpResponse.empty(HttpStatus.OK)
        response.set_header("X-Frame-Options", "ALLOWALL")  # simule un handler amont
        response.force_security_header("X-Frame-Options", "SAMEORIGIN")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")

    def test_set_header_does_not_override_by_itself(self):
        response = HttpResponse.empty(HttpStatus.NOT_FOUND)
        response.set_header("Content-Type", "text/html")
        self.assertEqual(response.headers["Content-Type"], "text/html")
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_accepts_arbitrary_int_status_not_in_httpstatus(self):
        # Necessaire pour FastCGI (Phase 8) : un script PHP peut renvoyer
        # un code (201, 204, 422...) hors de l'enumeration fermee HttpStatus.
        response = HttpResponse.empty(201)
        self.assertEqual(response.status, 201)


class TestReasonPhraseFor(unittest.TestCase):
    def test_known_httpstatus_code(self):
        from omega_serv.domain.http.status_codes import reason_phrase_for
        self.assertEqual(reason_phrase_for(HttpStatus.NOT_FOUND), "Not Found")

    def test_code_outside_httpstatus_falls_back_to_stdlib(self):
        import http

        from omega_serv.domain.http.status_codes import reason_phrase_for
        self.assertEqual(reason_phrase_for(201), "Created")
        self.assertEqual(reason_phrase_for(422), http.HTTPStatus(422).phrase)

    def test_truly_unknown_code_returns_empty_string(self):
        from omega_serv.domain.http.status_codes import reason_phrase_for
        self.assertEqual(reason_phrase_for(499), "")


if __name__ == "__main__":
    unittest.main()
