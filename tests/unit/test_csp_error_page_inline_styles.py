import base64
import hashlib
import unittest
from pathlib import Path

from omega_serv.domain.security.csp import (
    DEFAULT_CSP_POLICY,
    allow_inline_styles_by_hash,
    parse_csp_directives,
)


def _token(css: bytes) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(css).digest()).decode() + "'"


class TestAllowInlineStylesByHash(unittest.TestCase):
    def test_style_block_hash_added_to_style_src(self):
        css = b"\n  body { color: red; }\n"
        policy = allow_inline_styles_by_hash(DEFAULT_CSP_POLICY, b"<html><style>" + css + b"</style></html>")
        style_src = parse_csp_directives(policy)["style-src"].split()
        self.assertEqual(style_src, ["'self'", _token(css)])

    def test_never_unsafe_inline(self):
        policy = allow_inline_styles_by_hash(DEFAULT_CSP_POLICY, b"<style>a{}</style>")
        self.assertNotIn("unsafe-inline", policy)

    def test_other_directives_unchanged_and_in_order(self):
        policy = allow_inline_styles_by_hash(DEFAULT_CSP_POLICY, b"<style>a{}</style>")
        before = parse_csp_directives(DEFAULT_CSP_POLICY)
        after = parse_csp_directives(policy)
        self.assertEqual(list(before), list(after))
        for name in before:
            if name != "style-src":
                self.assertEqual(before[name], after[name])

    def test_each_block_hashed_once(self):
        html = b"<style>a{}</style><STYLE media='x'>b{}</STYLE><style>a{}</style>"
        style_src = parse_csp_directives(allow_inline_styles_by_hash(DEFAULT_CSP_POLICY, html))["style-src"].split()
        self.assertEqual(style_src, ["'self'", _token(b"a{}"), _token(b"b{}")])

    def test_no_style_block_policy_unchanged(self):
        self.assertEqual(allow_inline_styles_by_hash(DEFAULT_CSP_POLICY, b"<p>404</p>"), DEFAULT_CSP_POLICY)

    def test_unsafe_inline_kept_without_hash(self):
        policy = "default-src 'none'; style-src 'self' 'unsafe-inline'"
        self.assertEqual(allow_inline_styles_by_hash(policy, b"<style>a{}</style>"), policy)

    def test_explicit_none_respected(self):
        policy = "default-src 'none'; style-src 'none'"
        self.assertEqual(allow_inline_styles_by_hash(policy, b"<style>a{}</style>"), policy)

    def test_falls_back_to_default_src(self):
        policy = allow_inline_styles_by_hash("default-src 'self'; img-src 'self'", b"<style>a{}</style>")
        self.assertEqual(parse_csp_directives(policy)["style-src"], "'self' " + _token(b"a{}"))
        self.assertEqual(parse_csp_directives(policy)["default-src"], "'self'")

    def test_no_style_or_default_src_unchanged(self):
        policy = "img-src 'self'"
        self.assertEqual(allow_inline_styles_by_hash(policy, b"<style>a{}</style>"), policy)

    def test_hash_matches_browser_for_real_error_page(self):
        """Modele fourni par l'utilisateur (~/DEV/SERV/errors/429.html) si present : le texte
        exact entre <style> et </style> est ce que le navigateur hache."""
        page = Path.home() / "DEV/SERV/errors/429.html"
        if not page.is_file():
            self.skipTest("modele 429.html absent")
        html = page.read_bytes()
        start = html.index(b"<style>") + len(b"<style>")
        css = html[start:html.index(b"</style>")]
        self.assertIn(_token(css), allow_inline_styles_by_hash(DEFAULT_CSP_POLICY, html))


if __name__ == "__main__":
    unittest.main()
