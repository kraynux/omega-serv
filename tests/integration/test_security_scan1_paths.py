# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan de securite n° 1 du 2026-11-20, causes A et B : les zones d'authentification et les regles d'acces se
decident sur le chemin canonique, celui du fichier servi - dans les deux moteurs, serveur reel.

Avant : `//private/x`, `/%70rivate/x`, `/private%2fx` ou `/private\\x` echappaient a la zone `/private` et
servaient le fichier sans identifiants ; `/pub/%252e%252e/.env` sortait d'une zone `allow` et levait le refus des
fichiers caches."""
import json
import unittest

from tests.integration.proxy_harness import (
    NATIVE_BINARY,
    USER,
    ProxyProject,
    ScriptedBackend,
    basic,
)

_PROTECTED_SPELLINGS = (
    "/private/doc.txt", "//private/doc.txt", "/%70rivate/doc.txt", "/%2570rivate/doc.txt",
    "/private%2fdoc.txt", "/private%5Cdoc.txt", "/private\\doc.txt", "/./private/doc.txt",
)
_DENIED_SPELLINGS = ("/secret/x.txt", "//secret/x.txt", "/%73ecret/x.txt", "/secret%2Fx.txt", "/SECRET/../secret/x.txt")


class _PathCanonicalisation:
    ENGINE = "python"

    def setUp(self):
        self.backend = ScriptedBackend()
        self.addCleanup(self.backend.stop)
        self.project = ProxyProject(self.ENGINE, self.backend.port, options={
            "auth": {"enabled": True},
            "access_control": {"enabled": True, "list": [
                {"path_prefix": "/secret/", "verdict": "deny"},
                {"path_prefix": "/pub/", "verdict": "allow"},
            ]},
        })
        webroot = self.project.root / "webroot"
        for folder in ("private", "secret", "pub"):
            (webroot / folder).mkdir()
        (webroot / "private" / "doc.txt").write_text("document prive")
        (webroot / "secret" / "x.txt").write_text("secret")
        (webroot / "pub" / "a.txt").write_text("public")
        (webroot / ".env").write_text("MOT_DE_PASSE=1")
        (webroot / "a b.txt").write_text("espace")
        zones = self.project.root / "secure" / "auth" / "zones.json"
        data = json.loads(zones.read_text())
        data["zones"].append({"path_prefix": "/private", "realm": "Prive", "allowed_users": [USER]})
        zones.write_text(json.dumps(data))
        self.project.start()
        self.addCleanup(self.project.stop)
        if self.ENGINE == "native":
            self.assertEqual(self.project.effective_engine(), "native")

    def _status(self, target: str, headers: list[str] | None = None) -> int:
        return self.project.request("GET", target, headers=headers)[0]

    def test_auth_zone_holds_for_every_spelling(self):
        for target in _PROTECTED_SPELLINGS:
            with self.subTest(target=target):
                self.assertIn(self._status(target), (400, 401))
        self.assertEqual(self._status("/%70rivate/doc.txt"), 401)
        self.assertEqual(self._status("//private/doc.txt"), 401)

    def test_auth_zone_still_serves_with_credentials(self):
        self.assertEqual(self._status("/private/doc.txt", [f"Authorization: {basic()}"]), 200)

    def test_deny_rule_holds_for_every_spelling(self):
        for target in _DENIED_SPELLINGS:
            with self.subTest(target=target):
                self.assertIn(self._status(target), (400, 403))
        self.assertEqual(self._status("/%73ecret/x.txt"), 403)

    def test_double_encoded_dot_segment_is_refused(self):
        for target in ("/pub/%252e%252e/.env", "/pub/%2e%2e/.env", "/pub/%252E%252E%252F.env"):
            with self.subTest(target=target):
                self.assertEqual(self._status(target), 400)
        self.assertEqual(self._status("/pub/a.txt"), 200)
        self.assertEqual(self._status("/.env"), 403)

    def test_unusable_encoding_is_refused(self):
        for target in ("/%FF.txt", "/a%00b"):
            with self.subTest(target=target):
                self.assertEqual(self._status(target), 400)

    def test_encoded_names_still_served(self):
        self.assertEqual(self._status("/a%20b.txt"), 200)
        self.assertEqual(self._status("/%70ub/a.txt"), 200)

    def test_proxy_auth_zone_holds_for_encoded_spelling(self):
        self.assertEqual(self._status("/api/%70rive/x"), 401)
        self.assertEqual(self._status("/api//prive/x"), 401)
        self.assertEqual(self.backend.hits_for("/api/%70rive/x") + self.backend.hits_for("/api//prive/x"), 0)


class TestPathCanonicalisationPython(_PathCanonicalisation, unittest.TestCase):
    ENGINE = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestPathCanonicalisationNative(_PathCanonicalisation, unittest.TestCase):
    ENGINE = "native"


if __name__ == "__main__":
    unittest.main()
