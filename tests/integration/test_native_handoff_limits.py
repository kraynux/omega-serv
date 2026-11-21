# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Connexions confiees par le moteur natif au processus de securite (plan proxy natif v2, lot 1 : D9, D11).

- D9 : une connexion confiee ne comptait dans aucune limite `max_connections`.
- D11 : SIGTERM tuait aussitot le processus de securite - une requete proxifiee en cours etait coupee net, sans
  le delai de grace dont profitent les connexions du natif."""
from __future__ import annotations

import signal
import threading
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeHandoffLimits(unittest.TestCase):
    def setUp(self):
        self.backend = ScriptedBackend()
        self.addCleanup(self.backend.stop)

    def _project(self, **server) -> ProxyProject:
        project = ProxyProject("native", self.backend.port, server=server, zone={"read_timeout_seconds": 5})
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), "native")
        return project

    def test_handed_off_connections_count_in_max_connections(self):
        project = self._project(max_connections=1)
        slow: dict[str, int] = {}
        holder = threading.Thread(target=lambda: slow.update(status=project.request("GET", "/api/slow")[0]))
        holder.start()
        time.sleep(0.8)  # la premiere connexion est confiee a Python et attend le backend (3 s)
        second = project.request("GET", "/api/ok")[0]
        holder.join(10)
        self.assertEqual(slow.get("status"), 200)
        self.assertEqual(second, 503)

    def test_sigterm_lets_a_handed_off_request_finish(self):
        project = self._project(shutdown_grace_period_seconds=8)
        result: dict[str, object] = {}
        client = threading.Thread(target=lambda: result.update(answer=project.request("GET", "/api/slow", timeout=12)))
        client.start()
        time.sleep(0.8)
        assert project.process is not None
        project.process.send_signal(signal.SIGTERM)
        client.join(15)
        status, _headers, body, _raw = result["answer"]  # type: ignore[misc]
        self.assertEqual((status, body), (200, b"lent"))


if __name__ == "__main__":
    unittest.main()
