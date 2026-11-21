# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan de securite n° 1 du 2026-11-20, F8 : un client qui nommait `Content-Length` dans `Connection` faisait retirer
la longueur alors que son corps partait vers le backend, qui le lisait comme une seconde requete (contrebande).
La longueur est desormais recalculee sur le corps transmis - moteur Python et relais natif, serveur reel."""
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend

_SMUGGLED = b"GET /api/smuggled HTTP/1.1\r\nHost: interne\r\n\r\n"


class _ProxyFraming:
    ENGINE = "python"

    def setUp(self):
        self.backend = ScriptedBackend()
        self.addCleanup(self.backend.stop)
        self.project = ProxyProject(self.ENGINE, self.backend.port,
                                    proxy={"engine": "native"} if self.ENGINE == "native" else None)
        self.project.start()
        self.addCleanup(self.project.stop)

    def _heads_for(self, path: str) -> list[bytes]:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not self.backend.requests_for(path):
            time.sleep(0.05)
        return self.backend.requests_for(path)

    def test_length_named_in_connection_is_recomputed(self):
        status = self.project.request("POST", "/api/ok", headers=["Connection: close, Content-Length"],
                                      body=_SMUGGLED)[0]
        self.assertEqual(status, 200)
        heads = self._heads_for("/api/ok")
        self.assertEqual(len(heads), 1)
        self.assertIn(f"Content-Length: {len(_SMUGGLED)}\r\n".encode(), heads[0])
        time.sleep(0.3)
        self.assertEqual(self.backend.hits_for("/api/smuggled"), 0)

    def test_bodiless_get_gets_no_length(self):
        self.assertEqual(self.project.request("GET", "/api/ok")[0], 200)
        heads = self._heads_for("/api/ok")
        self.assertNotIn(b"content-length", heads[0].lower())


class TestProxyFramingPython(_ProxyFraming, unittest.TestCase):
    ENGINE = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestProxyFramingNative(_ProxyFraming, unittest.TestCase):
    ENGINE = "native"


if __name__ == "__main__":
    unittest.main()
