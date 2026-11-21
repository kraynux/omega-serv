# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Decision de l'auteur du 2026-11-16 (choix a) : un appel accepte a `/.omega-serv-admin/` (TUI, administration web)
n'est jamais ecrit dans access.log ; refuse (403, hors des reseaux de confiance), il reste ecrit pour omega-jail et
RIPOSTE. De bout en bout, dans les deux moteurs. Sans binaire natif, la moitie native est sautee."""
from __future__ import annotations

import time
import unittest

from omega_serv.infrastructure.server.asyncio_server import is_internal_admin_call
from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject


def _access_log(project: ProxyProject, expected: str | None = None, timeout: float = 5.0) -> str:
    path = project.root / "var" / "log" / "access.log"
    deadline = time.monotonic() + timeout
    while True:
        content = path.read_text() if path.exists() else ""
        if expected is None or expected in content or time.monotonic() > deadline:
            return content
        time.sleep(0.1)


class _Case:
    engine = "python"

    def _project(self, trusted: list[str]) -> ProxyProject:
        project = ProxyProject(self.engine, 9, proxy={"engine": "native"} if self.engine == "native" else None,
                               options={"trusted_proxy": {"enabled": True, "trusted_networks": trusted,
                                                          "header_preference": ["X-Forwarded-For"]}})
        self.addCleanup(project.stop)
        project.start()
        return project

    def test_accepted_internal_call_is_not_logged(self):
        project = self._project(["127.0.0.1/32"])
        self.assertEqual(project.request("GET", "/.omega-serv-admin/backends")[0], 200)
        self.assertEqual(project.request("GET", "/")[0], 200)
        log = _access_log(project, '"GET / HTTP/1.1"')
        self.assertIn('"GET / HTTP/1.1"', log)  # le reste est toujours ecrit
        self.assertNotIn("/.omega-serv-admin/", log)

    def test_relayed_call_is_refused(self):
        """Scan de securite n° 1 (F20/F25/F30) : pair de confiance, mais requete relayee par un proxy de la meme
        machine (en-tete de relais present) - refusee, sur les deux routes internes et dans les deux moteurs."""
        project = self._project(["127.0.0.1/32"])
        self.assertEqual(project.request("GET", "/.omega-serv-admin/backends", forwarded=True)[0], 403)
        self.assertEqual(project.request("GET", "/.omega-serv-admin/backends",
                                         headers=["Forwarded: for=203.0.113.9"])[0], 403)
        self.assertEqual(project.request("GET", "/.omega-serv-load/", forwarded=True)[0], 403)
        self.assertEqual(project.request("GET", "/.omega-serv-admin/backends")[0], 200)

    def test_refused_call_stays_in_the_log(self):
        project = self._project(["10.0.0.0/8"])  # 127.0.0.1 hors des reseaux de confiance
        self.assertEqual(project.request("GET", "/.omega-serv-admin/backends")[0], 403)
        self.assertIn('"GET /.omega-serv-admin/backends HTTP/1.1" 403', _access_log(project, "omega-serv-admin"))


class TestPythonEngine(_Case, unittest.TestCase):
    engine = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeEngine(_Case, unittest.TestCase):
    engine = "native"


class TestRule(unittest.TestCase):
    def test_rule(self):
        self.assertTrue(is_internal_admin_call("/.omega-serv-admin/health", 200))
        self.assertTrue(is_internal_admin_call("/.omega-serv-admin/backends", 404))
        self.assertFalse(is_internal_admin_call("/.omega-serv-admin/backends", 403))
        self.assertFalse(is_internal_admin_call("/autre", 200))


if __name__ == "__main__":
    unittest.main()
