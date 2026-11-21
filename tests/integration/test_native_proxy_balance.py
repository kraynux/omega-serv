# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 6 : equilibrage, sante et noms DNS dans le relais natif, de bout en bout (vrais backends,
`omega-serv serve` reel avec reverse_proxy.engine = native), compare au moteur Python quand le resultat doit etre le
meme.

- repartition, cookie collant et regles par en-tete : memes backends que Python ;
- plafond max_concurrent_requests : 503 ;
- backend injoignable : nouvel essai sur l'autre (GET), backend marque hors service ;
- etat manuel pose par l'administration (processus n° 0) : applique par le natif, relu par l'administration ;
- nom DNS : une adresse = un backend, adresses ecrites dans error.log ; nom non resolu : hors service.

Le binaire n'est pas versionne : sans build, ces tests sont sautes."""
from __future__ import annotations

import json
import socket
import threading
import time
import unittest
import urllib.request

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend, Streamed


def _named(name: str) -> bytes:
    body = name.encode()
    return b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def _held(conn: socket.socket, _head: bytes) -> bool:
    time.sleep(1.5)
    conn.sendall(_named("lent"))
    return True


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _extra(project: ProxyProject) -> dict:
    time.sleep(3.2)
    return json.loads((project.root / "var" / "run" / "engine-state.json").read_text())["extra"]


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestBalancingLikePython(unittest.TestCase):
    """Deux backends nommes A et B ; memes reponses attendues dans les deux moteurs."""

    def _project(self, engine: str, zone: dict, backends: int = 2) -> tuple[ProxyProject, list[ScriptedBackend]]:
        servers = [ScriptedBackend({"/api/qui": _named(name), "/api/lent": Streamed(_held)}) for name in "AB"[:backends]]
        for server in servers:
            self.addCleanup(server.stop)
        upstreams = [{"host": "127.0.0.1", "port": s.port, **extra}
                     for s, extra in zip(servers, zone.pop("extras", [{}] * backends), strict=True)]
        if "rule_to" in zone:  # regle par en-tete vers le backend d'indice donne
            zone["routing_rules"] = [{"header_name": "X-Version", "pattern": "be*",
                                      "upstream_key": f"127.0.0.1:{servers[zone.pop('rule_to')].port}"}]
        project = ProxyProject(engine, servers[0].port, zone={"upstreams": upstreams, "read_timeout_seconds": 5, **zone},
                               proxy={"engine": "native"} if engine == "native" else None)
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), engine)
        return project, servers

    def _who(self, project: ProxyProject, headers: list[str] | None = None) -> tuple[str, dict]:
        _status, response_headers, body, _raw = project.request("GET", "/api/qui", headers=headers)
        return body.decode(), response_headers

    def test_round_robin_and_weights(self):
        for zone, expected in (({}, ["A", "B", "A", "B", "A", "B"]),
                               ({"load_balancing": "weighted_round_robin", "extras": [{"weight": 2}, {}]},
                                ["A", "B", "A", "A", "B", "A"])):
            results = {}
            for engine in ("python", "native"):
                project, _servers = self._project(engine, dict(zone, extras=list(zone.get("extras", [{}, {}]))))
                results[engine] = [self._who(project)[0] for _ in range(6)]
            self.assertEqual(results["native"], results["python"], zone)
            self.assertEqual(results["native"], expected)

    def test_sticky_cookie_and_header_rule(self):
        for engine in ("python", "native"):
            with self.subTest(engine=engine):
                project, _servers = self._project(engine, {"sticky_session_enabled": True, "rule_to": 1})
                first, headers = self._who(project)
                cookie = next(c for c in headers["set-cookie"] if c.startswith("omega_proxy_sticky="))
                self.assertIn("HttpOnly", cookie)
                value = cookie.split(";", 1)[0]
                self.assertEqual({self._who(project, [f"Cookie: {value}"])[0] for _ in range(4)}, {first})
                # Regle d'en-tete avant le cookie (§27.2) : toujours B.
                self.assertEqual({self._who(project, ["X-Version: beta", f"Cookie: {value}"])[0] for _ in range(3)},
                                 {"B"})

    def test_capacity_gives_503(self):
        project, _servers = self._project("native", {"extras": [{"max_concurrent_requests": 1}]}, backends=1)
        statuses: list[int] = []
        slow = threading.Thread(target=lambda: statuses.append(project.request("GET", "/api/lent")[0]))
        slow.start()
        time.sleep(0.4)  # la premiere requete occupe la seule place
        self.assertEqual(project.request("GET", "/api/qui")[0], 503)
        slow.join()
        self.assertEqual(statuses, [200])
        self.assertEqual(project.request("GET", "/api/qui")[0], 200)  # place rendue

    def test_capacity_is_exact_across_threads(self):
        # C9 : choix et reservation sous le verrou de la zone - jamais plus de 2 requetes chez le backend, quel que
        # soit le fil qui les a acceptees (rafale parallele : EPOLLEXCLUSIVE reveille d'abord le fil 0).
        project, servers = self._project("native", {"extras": [{"max_concurrent_requests": 2}]}, backends=1)
        statuses: list[int] = []
        lock = threading.Lock()

        def one() -> None:
            status = project.request("GET", "/api/lent", timeout=10)[0]
            with lock:
                statuses.append(status)

        threads = [threading.Thread(target=one) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(statuses), [200, 200] + [503] * 6)
        self.assertEqual(servers[0].hits_for("/api/lent"), 2)

@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestHealthAndAdministration(unittest.TestCase):
    def setUp(self):
        self.live = ScriptedBackend({"/api/qui": _named("vivant")})
        self.addCleanup(self.live.stop)
        self.dead_port = _free_port()  # personne n'ecoute : connexion refusee
        self.project = ProxyProject("native", self.live.port, proxy={"engine": "native"}, zone={
            "upstreams": [{"host": "127.0.0.1", "port": self.dead_port}, {"host": "127.0.0.1", "port": self.live.port}],
            "unhealthy_after": 2})
        self.addCleanup(self.project.stop)
        self.project.start()

    def _admin(self, method: str, query: str) -> dict:
        request = urllib.request.Request(f"http://127.0.0.1:{self.project.port}/.omega-serv-admin/health?{query}",
                                         method=method)
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def test_dead_backend_is_retried_then_marked_down(self):
        bodies = [self.project.request("GET", "/api/qui")[2] for _ in range(6)]
        self.assertEqual(bodies, [b"vivant"] * 6)  # C8 : GET rejoue sur l'autre backend, jamais un 502
        extra = _extra(self.project)
        self.assertGreaterEqual(int(extra["upstream_retries"]), 1)
        dead = f"127.0.0.1:{self.dead_port}"
        self.assertEqual(self._admin("GET", "zone=/api/")["upstreams"][dead], "down")  # etat du natif, relu par n° 0


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestManualStates(unittest.TestCase):
    def test_draining_set_by_the_administration_applies_to_the_native_engine(self):
        servers = [ScriptedBackend({"/api/qui": _named(name)}) for name in "AB"]
        for server in servers:
            self.addCleanup(server.stop)
        project = ProxyProject("native", servers[0].port, proxy={"engine": "native"}, zone={
            "upstreams": [{"host": "127.0.0.1", "port": s.port} for s in servers]})
        self.addCleanup(project.stop)
        project.start()

        def admin(method: str, query: str) -> dict:
            request = urllib.request.Request(f"http://127.0.0.1:{project.port}/.omega-serv-admin/health?{query}",
                                             method=method)
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read())

        a = f"127.0.0.1:{servers[0].port}"
        self.assertEqual(admin("POST", f"zone=/api/&upstream={a}&status=draining")["status"], "draining")
        time.sleep(0.3)  # trame BACKEND_EVENT appliquee a tous les fils du natif
        self.assertEqual({project.request("GET", "/api/qui")[2] for _ in range(6)}, {b"B"})
        self.assertEqual(admin("GET", "zone=/api/")["upstreams"][a], "draining")
        time.sleep(1.5)  # etat relu chez le natif (environ 1 fois/s)
        self.assertEqual(admin("GET", "zone=/api/")["backends"][a], "draining")
        admin("POST", f"zone=/api/&upstream={a}&status=clear")
        time.sleep(0.3)
        self.assertEqual({project.request("GET", "/api/qui")[2] for _ in range(6)}, {b"A", b"B"})


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestDnsNames(unittest.TestCase):
    def test_name_resolved_once_each_address_a_backend(self):
        backend = ScriptedBackend({"/api/qui": _named("par-nom")})
        self.addCleanup(backend.stop)
        project = ProxyProject("native", backend.port, proxy={"engine": "native"},
                               zone={"upstreams": [{"host": "localhost", "port": backend.port}]})
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), "native")
        # localhost : 127.0.0.1 (le backend) et souvent ::1 (personne) - l'adresse morte est rejouee puis ecartee.
        self.assertEqual({project.request("GET", "/api/qui")[2] for _ in range(4)}, {b"par-nom"})
        errors = (project.root / "var" / "log" / "error.log").read_text()
        self.assertIn(f"reverse proxy : localhost:{backend.port} résolu en ", errors)
        self.assertIn("127.0.0.1", errors)

    def test_unresolved_name_is_out_of_service(self):
        backend = ScriptedBackend({"/api/qui": _named("ip")})
        self.addCleanup(backend.stop)
        project = ProxyProject("native", backend.port, proxy={"engine": "native"}, zone={"upstreams": [
            {"host": "omega-serv-inexistant.invalid", "port": 80}, {"host": "127.0.0.1", "port": backend.port}]})
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), "native")  # decision de l'auteur : demarre quand meme
        self.assertEqual([project.request("GET", "/api/qui")[2] for _ in range(3)], [b"ip"] * 3)
        errors = (project.root / "var" / "log" / "error.log").read_text()
        self.assertIn("omega-serv-inexistant.invalid:80 ne se résout pas : backend hors service", errors)


if __name__ == "__main__":
    unittest.main()
