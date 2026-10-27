"""Les classes CSS des pages d'erreur integrees existent dans leur feuille de style.
Regression du lot 3 i18n (2026-10-21) : `theme-orange` / `theme-cyan` accentues par l'outil
d'accents -> plus aucun style applique aux pages 403/404."""
from __future__ import annotations

import re
import unittest

from omega_serv.domain.http.error_pages import (
    _CURATED_TEMPLATES,
    error_pages_css,
    render_default_error_page,
)


class TestErrorPageClasses(unittest.TestCase):
    def test_every_class_used_is_styled(self):
        css = error_pages_css()
        for status in _CURATED_TEMPLATES:
            page = render_default_error_page(status)
            for classes in re.findall(r'class="([^"]+)"', page.decode()):
                for name in classes.split():
                    with self.subTest(status=status, css_class=name):
                        self.assertRegex(css, rf"\.{re.escape(name)}\b")

    def test_class_names_are_ascii(self):
        for status in _CURATED_TEMPLATES:
            page = render_default_error_page(status)
            for classes in re.findall(r'class="([^"]+)"', page.decode()):
                self.assertTrue(classes.isascii(), classes)


if __name__ == "__main__":
    unittest.main()
