"""Forme absolue de la cible de requete (RFC 9112 §3.2.2 ; plan moteur C++ §14, validee 2026-11-02)."""
import unittest

from omega_serv.domain.http.request import InvalidAbsoluteTarget, absolute_form_parts


class TestAbsoluteFormParts(unittest.TestCase):
    def test_origin_form_untouched(self):
        for target in ("/", "/a?b", "*", "ftp://h/x", "http:/h/x", "httpx://h/"):
            self.assertIsNone(absolute_form_parts(target), target)

    def test_absolute_form(self):
        cases = {
            "http://h/a/b?c=d": ("h", "/a/b?c=d"),
            "HTTPS://h:8443/a": ("h:8443", "/a"),
            "hTtP://h": ("h", "/"),
            "http://h?q": ("h", "/?q"),
            "http://[::1]:80/x": ("[::1]:80", "/x"),
            "http://h//x": ("h", "//x"),
        }
        for target, expected in cases.items():
            self.assertEqual(absolute_form_parts(target), expected, target)

    def test_invalid_host_rejected(self):
        for target in ("http://", "http:///a", "http://?q", "http://u@h/", "http://a b/", "http://a\tb/",
                       "http://a\nb/", "http://a\x7fb/"):
            with self.assertRaises(InvalidAbsoluteTarget, msg=target):
                absolute_form_parts(target)


if __name__ == "__main__":
    unittest.main()
