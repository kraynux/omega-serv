# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan de securite n° 2 du 2026-11-20, serveur reel, deux moteurs :
- F1-F3 : `GET private/x` (cible sans « / » initial) echappait a la zone d'authentification et servait le fichier ;
- F15 : `..;` sortait de la zone proxy vers un backend Java ;
- F16 : le cookie de session de l'administration web partait au backend ;
- F45 : des requetes en pipeline traitees par recursion pouvaient epuiser la pile du moteur natif."""
import json
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, USER, ProxyProject, ScriptedBackend


class _Scan2:
    ENGINE = "python"

    def setUp(self):
        self.backend = ScriptedBackend()
        self.addCleanup(self.backend.stop)
        self.project = ProxyProject(self.ENGINE, self.backend.port, options={"auth": {"enabled": True}},
                                    server={"max_keepalive_requests": 5000},
                                    proxy={"engine": "native"} if self.ENGINE == "native" else None)
        (self.project.root / "webroot" / "private").mkdir()
        (self.project.root / "webroot" / "private" / "doc.txt").write_text("document prive")
        zones = self.project.root / "secure" / "auth" / "zones.json"
        data = json.loads(zones.read_text())
        data["zones"].append({"path_prefix": "/private", "realm": "Prive", "allowed_users": [USER]})
        zones.write_text(json.dumps(data))
        self.project.start()
        self.addCleanup(self.project.stop)

    def test_relative_target_is_refused(self):
        for target in ("private/doc.txt", "private\\doc.txt", "%2Fprivate/doc.txt"):
            with self.subTest(target=target):
                status, _headers, body, _raw = self.project.request("GET", target)
                self.assertEqual(status, 400)
                self.assertNotIn(b"document prive", body)
        self.assertEqual(self.project.request("GET", "/private/doc.txt")[0], 401)

    def test_path_parameter_dot_segment_never_reaches_backend(self):
        self.assertEqual(self.project.request("GET", "/api/..;x/admin")[0], 400)
        time.sleep(0.2)
        self.assertEqual(self.backend.hits_for("/api/..;x/admin"), 0)

    def test_admin_session_cookie_never_reaches_backend(self):
        status = self.project.request("GET", "/api/ok", headers=["Cookie: s=1; omega_admin=jeton-secret"])[0]
        self.assertEqual(status, 200)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not self.backend.requests_for("/api/ok"):
            time.sleep(0.05)
        head = self.backend.requests_for("/api/ok")[0]
        self.assertNotIn(b"jeton-secret", head)
        self.assertIn(b"s=1", head)

    def test_many_pipelined_requests_are_all_answered(self):
        count = 3000
        one = f"GET /index.html HTTP/1.1\r\nHost: 127.0.0.1:{self.project.port}\r\n\r\n".encode()
        last = f"GET /index.html HTTP/1.1\r\nHost: 127.0.0.1:{self.project.port}\r\nConnection: close\r\n\r\n".encode()
        raw = self.project.exchange(one * (count - 1) + last, timeout=30)
        self.assertEqual(raw.count(b"HTTP/1.1 200"), count)
        self.assertEqual(self.project.request("GET", "/index.html")[0], 200)  # serveur toujours debout


class TestScan2Python(_Scan2, unittest.TestCase):
    ENGINE = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestScan2Native(_Scan2, unittest.TestCase):
    ENGINE = "native"


if __name__ == "__main__":
    unittest.main()
