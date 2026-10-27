"""Pages servies aux visiteurs dans la langue choisie (plan i18n D19)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_lib.i18n.policies import language_for

from omega_serv.application.server.resolve_error_page import resolve_error_page_body
from omega_serv.core.i18n import PAGE_STATE, STATE, page_html_lang
from omega_serv.domain.http.error_pages import render_default_error_page
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _Fixed:
    """Catalogue minimal : traduit une phrase connue."""

    def __init__(self, mapping):
        self.mapping = mapping

    def gettext(self, message):
        return self.mapping.get(message, message)

    def ngettext(self, s, p, n):
        return s if n == 1 else p


class TestVisitorPagesLanguage(unittest.TestCase):
    def tearDown(self):
        PAGE_STATE.reset()
        STATE.reset()

    def test_french_by_default(self):
        self.assertEqual(page_html_lang(), "fr")
        self.assertIn(b'lang="fr"', render_default_error_page(404))

    def test_page_text_and_lang_follow_page_language_only(self):
        PAGE_STATE.install(language_for("zh_CN"), _Fixed({"404 - Page non trouvée": "404 - 页面未找到"}))
        page = render_default_error_page(404).decode()
        self.assertIn('lang="zh-CN"', page)
        self.assertIn("404 - 页面未找到", page)
        self.assertEqual(STATE.language.code, "fr", "la langue des journaux/interface n'est pas touchee")

    def test_arabic_pages_are_right_to_left(self):
        self.assertIn(b'dir="ltr"', render_default_error_page(404))
        PAGE_STATE.install(language_for("ar"), _Fixed({}))
        for status in (401, 403, 404, 429, 451, 500):
            with self.subTest(status=status):
                page = render_default_error_page(status).decode()
                self.assertIn('lang="ar" dir="rtl"', page)

    def test_translation_is_html_escaped(self):
        PAGE_STATE.install(language_for("en"), _Fixed({"← Retour à l'index": "<b>Back</b> & home"}))
        page = render_default_error_page(404).decode()
        self.assertIn("&lt;b&gt;Back&lt;/b&gt; &amp; home", page)
        self.assertNotIn("<b>Back</b>", page)

    def test_custom_page_per_language_then_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "404.html").write_bytes(b"generique")
            fs = LocalFilesystem()
            self.assertEqual(resolve_error_page_body(404, root, fs), b"generique")
            PAGE_STATE.install(language_for("en"), _Fixed({}))
            self.assertEqual(resolve_error_page_body(404, root, fs), b"generique", "pas de 404-en.html : repli")
            (root / "404-en.html").write_bytes(b"english")
            self.assertEqual(resolve_error_page_body(404, root, fs), b"english")


if __name__ == "__main__":
    unittest.main()
