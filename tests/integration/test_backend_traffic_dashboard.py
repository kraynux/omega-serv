# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tableau de bord par type d'instance (Projets 3.0.0 §9, chantier 3, decision de l'auteur du 2026-11-16) : mesures
par backend lues par `/.omega-serv-admin/backends`, de bout en bout (vrais backends, `omega-serv serve` reel), dans
les deux moteurs, avec les memes resultats :

- requetes = tentatives envoyees a chaque backend (un nouvel essai compte chez l'autre) ;
- backend injoignable = 502 compte chez lui ; delai de lecture depasse = 504 ;
- etat, temps moyen, requetes en cours.

Le binaire natif n'est pas versionne : sans build, la moitie native est sautee."""
from __future__ import annotations

import json
import socket
import time
import unittest
import urllib.request

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend, Streamed


def _named(name: str) -> bytes:
    body = name.encode()
    return b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def _too_slow(conn: socket.socket, _head: bytes) -> bool:
    time.sleep(2.0)  # au-dela de read_timeout_seconds = 1 : 504
    conn.sendall(_named("trop tard"))
    return True


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class _DashboardCase:
    engine = "python"

    def setUp(self):
        self.live = ScriptedBackend({"/api/qui": _named("vivant"), "/api/lent": Streamed(_too_slow)})
        self.addCleanup(self.live.stop)
        self.dead_port = _free_port()  # personne n'ecoute : connexion refusee
        self.project = ProxyProject(
            self.engine, self.live.port, proxy={"engine": "native"} if self.engine == "native" else None,
            zone={"upstreams": [{"host": "127.0.0.1", "port": self.dead_port},
                                {"host": "127.0.0.1", "port": self.live.port}],
                  "unhealthy_after": 2, "read_timeout_seconds": 1})
        self.addCleanup(self.project.stop)
        self.project.start()
        self.assertEqual(self.project.effective_engine(), self.engine)

    def _backends(self) -> dict[str, dict]:
        url = f"http://127.0.0.1:{self.project.port}/.omega-serv-admin/backends"
        with urllib.request.urlopen(url, timeout=5) as response:
            rows = json.loads(response.read())["backends"]
        return {row["name"]: row for row in rows}

    def test_requests_errors_and_state_per_backend(self):
        bodies = [self.project.request("GET", "/api/qui")[2] for _ in range(6)]
        self.assertEqual(bodies, [b"vivant"] * 6)  # le GET est rejoue sur le backend vivant
        status = self.project.request("POST", "/api/lent", body=b"x")[0]  # POST : jamais rejoue
        if self.engine == "native":
            time.sleep(1.5)  # mesures relues chez le natif environ une fois par seconde
        rows = self._backends()
        dead, live = rows[f"127.0.0.1:{self.dead_port}"], rows[f"127.0.0.1:{self.live.port}"]
        expected_engine = "natif" if self.engine == "native" else "python"
        self.assertEqual({dead["engine"], live["engine"]}, {expected_engine})
        self.assertEqual(dead["zone"], "/api/")
        self.assertEqual(dead["status"], "down")
        self.assertGreaterEqual(dead["requests"], 2)
        self.assertEqual(dead["errors_502"], dead["requests"])  # chaque tentative vers le mort a echoue
        self.assertEqual(dead["errors_504"], 0)
        self.assertEqual(live["status"], "up")
        self.assertEqual(live["errors_502"], 0)
        if status == 504:  # le POST lent a pu partir vers le vivant (round-robin) : un 504 chez lui
            self.assertEqual(live["errors_504"], 1)
            self.assertEqual(live["requests"], 7)
        else:  # parti vers le mort (502), jamais rejoue
            self.assertEqual(status, 502)
            self.assertEqual(live["requests"], 6)
        self.assertIsNotNone(live["avg_ms"])
        self.assertEqual(live["active"], 0)

    def test_timeout_counts_as_504(self):
        statuses = [self.project.request("POST", "/api/lent", body=b"x")[0] for _ in range(4)]
        if self.engine == "native":
            time.sleep(1.5)
        live = self._backends()[f"127.0.0.1:{self.live.port}"]
        self.assertEqual(live["errors_504"], statuses.count(504))
        self.assertGreaterEqual(statuses.count(504), 1)


class TestPythonEngine(_DashboardCase, unittest.TestCase):
    engine = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeEngine(_DashboardCase, unittest.TestCase):
    engine = "native"


if __name__ == "__main__":
    unittest.main()
