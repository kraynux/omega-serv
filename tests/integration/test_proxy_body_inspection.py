# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Corps inspecte par le WAF selon la route (plan proxy natif v2, lot 1 : D34 / P9, D35), dans les deux moteurs.

- P9 : `waf.inspect.body_max_inspect_bytes` vaut sur toutes les routes ; le corps ENTIER n'est lu et inspecte que
  sur les routes qui le transmettent (proxy, FastCGI, envoi de fichiers). Avant, activer le reverse proxy faisait
  inspecter le corps entier sur toutes les routes, dans le moteur Python seulement (lien cache entre options).
- D35 : `waf.exclusions.do_not_inspect_body_path_prefixes`, propose par l'interface, n'etait lu nulle part.
- Lot 2 (Q3 revisee, decision de l'auteur du 2026-11-12) : le WAF n'inspecte plus que `body_max_inspect_bytes`,
  routes proxy comprises (le corps entier gelait le processus de securite : 2 Mo binaire = 6 s) ; au-dela, la suite
  passe sans inspection, ou 413 avec `body_over_limit = reject`."""
from __future__ import annotations

import os
import threading
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend

ATTACK = b"id=1 union select password from users"
PADDED = b"x=" + b"a" * 200 + b"&" + ATTACK  # attaque au-dela des 64 premiers octets


class _BodyInspection:
    ENGINE = "python"
    project: ProxyProject
    backend: ScriptedBackend

    @classmethod
    def setUpClass(cls):
        cls.backend = ScriptedBackend()
        cls.project = ProxyProject(cls.ENGINE, cls.backend.port, options={"waf": {
            "enabled": True, "mode": "block",
            "inspect": {"body_max_inspect_bytes": 64},
            "exclusions": {"do_not_inspect_body_path_prefixes": ["/api/libre"]},
        }})
        cls.project.start()

    @classmethod
    def tearDownClass(cls):
        cls.project.stop()
        cls.backend.stop()

    def post(self, target: str, body: bytes) -> int:
        return self.project.request("POST", target, ["Content-Type: application/x-www-form-urlencoded"], body)[0]

    def test_attack_within_the_limit_is_blocked_everywhere(self):
        self.assertEqual(self.post("/", ATTACK), 403)
        self.assertEqual(self.post("/api/ok", ATTACK), 403)

    def test_static_route_inspects_only_body_max_inspect_bytes(self):
        self.assertNotEqual(self.post("/", PADDED), 403)  # P9 : au-dela de la limite, comme le natif

    def test_proxy_route_inspects_only_body_max_inspect_bytes_but_forwards_everything(self):
        # Lot 2 (Q3 revisee) : avant, 403 - le corps entier etait inspecte sur les routes proxy.
        before = self.backend.hits_for("/api/ok")
        self.assertEqual(self.post("/api/ok", PADDED), 200)
        self.assertEqual(self.backend.hits_for("/api/ok"), before + 1)
        head = self.backend.requests_for("/api/ok")[-1]
        self.assertIn(f"content-length: {len(PADDED)}".encode(), head.lower())  # corps transmis entier

    def test_large_binary_body_does_not_freeze_the_security_stage(self):
        # Lot 2 : 4 Mo binaires vers une route proxy = environ 12 s de CPU en 2.6.2 (decodage et regles sur le corps
        # entier) ; un GET ordinaire envoye en meme temps attendait autant.
        body = os.urandom(4 * 1024 * 1024)
        result: dict[str, float] = {}

        def heavy() -> None:
            started = time.monotonic()
            self.project.request("POST", "/api/gros", ["Content-Type: application/octet-stream"], body, timeout=60)
            result["post"] = time.monotonic() - started
        thread = threading.Thread(target=heavy)
        thread.start()
        time.sleep(0.3)
        started = time.monotonic()
        self.assertEqual(self.project.request("GET", "/api/ok")[0], 200)
        result["get"] = time.monotonic() - started
        thread.join(60)
        self.assertLess(result["post"], 4.0)
        self.assertLess(result["get"], 2.0)

    def test_excluded_prefix_body_is_not_inspected_but_forwarded_whole(self):
        before = self.backend.hits_for("/api/libre")
        self.assertEqual(self.post("/api/libre", ATTACK), 200)
        self.assertEqual(self.backend.hits_for("/api/libre"), before + 1)
        head = self.backend.requests_for("/api/libre")[-1]
        self.assertIn(f"content-length: {len(ATTACK)}".encode(), head.lower())  # corps transmis entier
        self.assertEqual(self.post("/api/ok", ATTACK), 403)  # garde : les autres chemins restent inspectes


class TestBodyInspectionPythonEngine(_BodyInspection, unittest.TestCase):
    ENGINE = "python"


class _BodyOverLimitReject:
    """Lot 2 : `waf.inspect.body_over_limit = reject` - rien de non inspecte ne passe (413), sur toutes les routes."""
    ENGINE = "python"
    project: ProxyProject
    backend: ScriptedBackend

    @classmethod
    def setUpClass(cls):
        cls.backend = ScriptedBackend()
        cls.project = ProxyProject(cls.ENGINE, cls.backend.port, options={"waf": {
            "enabled": True, "mode": "block",
            "inspect": {"body_max_inspect_bytes": 64, "body_over_limit": "reject"},
        }})
        cls.project.start()

    @classmethod
    def tearDownClass(cls):
        cls.project.stop()
        cls.backend.stop()

    def post(self, target: str, body: bytes) -> int:
        return self.project.request("POST", target, ["Content-Type: application/x-www-form-urlencoded"], body)[0]

    def test_body_over_the_inspected_size_is_refused_everywhere(self):
        before = self.backend.hits_for("/api/ok")
        self.assertEqual(self.post("/api/ok", PADDED), 413)
        self.assertEqual(self.post("/", PADDED), 413)
        self.assertEqual(self.backend.hits_for("/api/ok"), before)  # backend jamais atteint

    def test_body_within_the_inspected_size_is_judged_normally(self):
        self.assertEqual(self.post("/api/ok", ATTACK), 403)
        self.assertEqual(self.post("/api/ok", b"x=1"), 200)

    def test_refusal_is_explained_in_error_log(self):
        self.post("/api/ok", PADDED)
        errors = (self.project.root / "var" / "log" / "error.log").read_text()
        self.assertIn("corps plus grand que la partie inspectée par le WAF (waf.inspect.body_over_limit = reject)",
                      errors)


class TestBodyOverLimitRejectPythonEngine(_BodyOverLimitReject, unittest.TestCase):
    ENGINE = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestBodyOverLimitRejectNativeEngine(_BodyOverLimitReject, unittest.TestCase):
    ENGINE = "native"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestBodyInspectionNativeEngine(_BodyInspection, unittest.TestCase):
    ENGINE = "native"


if __name__ == "__main__":
    unittest.main()
