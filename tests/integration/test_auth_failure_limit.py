# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Serveur reel, deux moteurs (retour utilisateur 2026-11-20) : apres 10 mauvais mots de passe d'une adresse, refus
429 immediat SANS hachage ; un succes deja retenu passe toujours."""
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend, basic


class _Limit:
    ENGINE = "python"

    def setUp(self):
        self.backend = ScriptedBackend()
        self.addCleanup(self.backend.stop)
        self.project = ProxyProject(self.ENGINE, self.backend.port, options={"auth": {"enabled": True}},
                                    proxy={"engine": "native"} if self.ENGINE == "native" else None)
        self.project.start()
        self.addCleanup(self.project.stop)

    def _get(self, authorization: str) -> tuple[int, dict[str, list[str]]]:
        status, headers, _body, _raw = self.project.request("GET", "/api/prive/x",
                                                            headers=[f"Authorization: {authorization}"],
                                                            address="203.0.113.50")
        return status, headers

    def test_wrong_passwords_then_429_without_hashing(self):
        self.assertEqual(self._get(basic())[0], 200)  # succes retenu
        for _ in range(10):
            self.assertEqual(self._get(basic(password="faux"))[0], 401)
        started = time.monotonic()
        status, headers = self._get(basic(password="faux"))
        self.assertEqual(status, 429)
        self.assertLess(time.monotonic() - started, 0.25)  # aucun scrypt (~0,3 a 0,5 s)
        self.assertGreaterEqual(int(headers["retry-after"][0]), 1)
        self.assertEqual(self._get(basic())[0], 200)  # le visiteur legitime deja verifie passe toujours

    def test_threshold_from_the_authentication_menu(self):
        self.project.stop()
        self.project = ProxyProject(self.ENGINE, self.backend.port,
                                    options={"auth": {"enabled": True,  # reglages a plat dans l'option
                                                      "password_protection": {"failures_per_ip": 2}}},
                                    proxy={"engine": "native"} if self.ENGINE == "native" else None)
        self.project.start()
        self.addCleanup(self.project.stop)
        for _ in range(2):
            self.assertEqual(self._get(basic(password="faux"))[0], 401)
        self.assertEqual(self._get(basic(password="faux"))[0], 429)

class TestLimitPython(_Limit, unittest.TestCase):
    ENGINE = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestLimitNative(_Limit, unittest.TestCase):
    ENGINE = "native"


if __name__ == "__main__":
    unittest.main()
