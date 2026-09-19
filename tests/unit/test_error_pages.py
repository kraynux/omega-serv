import unittest

from omega_serv.domain.http.error_pages import render_default_error_page


class TestRenderDefaultErrorPage(unittest.TestCase):
    def test_includes_status_and_reason_phrase(self):
        body = render_default_error_page(400)
        self.assertIn(b"400", body)
        self.assertIn(b"Bad Request", body)

    def test_returns_valid_html_bytes(self):
        body = render_default_error_page(500)
        self.assertTrue(body.startswith(b"<!doctype html>"))
        self.assertIn(b"Internal Server Error", body)

    def test_unknown_code_falls_back_gracefully(self):
        body = render_default_error_page(599)
        self.assertIn(b"599", body)
        self.assertIn(b"<!doctype html>", body)


class TestCuratedDefaultPages(unittest.TestCase):
    def test_401_uses_the_curated_page(self):
        body = render_default_error_page(401)
        self.assertIn(b"401", body)
        self.assertIn("Non autorisé".encode(), body)

    def test_403_uses_the_curated_page(self):
        body = render_default_error_page(403)
        self.assertIn(b"403", body)
        self.assertIn("Accès interdit".encode(), body)

    def test_404_uses_the_curated_page(self):
        body = render_default_error_page(404)
        self.assertIn(b"404", body)
        self.assertIn("Page non trouvée".encode(), body)

    def test_451_uses_the_curated_page(self):
        body = render_default_error_page(451)
        self.assertIn(b"451", body)
        self.assertIn(b"banni", body)

    def test_curated_pages_never_leak_personal_contact_info(self):
        for status in (401, 403, 404, 451):
            body = render_default_error_page(status)
            self.assertNotIn(b"mailto:", body)
            self.assertNotIn(b"ts.net", body)


if __name__ == "__main__":
    unittest.main()
