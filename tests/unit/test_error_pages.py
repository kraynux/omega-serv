# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.http.error_pages import render_default_error_page


class TestRenderDefaultErrorPage(unittest.TestCase):
    def test_includes_status_and_reason_phrase(self):
        body = render_default_error_page(404)
        self.assertIn(b"404", body)
        self.assertIn(b"Not Found", body)

    def test_returns_valid_html_bytes(self):
        body = render_default_error_page(500)
        self.assertTrue(body.startswith(b"<!doctype html>"))
        self.assertIn(b"Internal Server Error", body)

    def test_unknown_code_falls_back_gracefully(self):
        body = render_default_error_page(599)
        self.assertIn(b"599", body)
        self.assertIn(b"<!doctype html>", body)


if __name__ == "__main__":
    unittest.main()
