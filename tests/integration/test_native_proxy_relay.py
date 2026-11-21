# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 4 : relais natif (options.reverse_proxy.engine = native) et connexion rendue au natif
(HANDOFF_DONE).

- D12 : une seule autorite pour la limite de debit - statique, zone relayee et zone confiee comptent dans le meme
  seau, dans les deux moteurs (avant : le natif et Python comptaient chacun de leur cote, limite doublee).
- Connexion confiee : rendue au natif apres la reponse ; la requete suivante (keep-alive) est servie par lui.
- C2, S16 : budgets du relais (503 immediat), et descripteurs stables apres de nombreux relais et retours (lot 5 :
  connexions inactives du pool mises a part).
- S22 : aucun octet vers le backend avant le verdict ; requete bloquee jamais relayee.

Le binaire n'est pas versionne : sans build (native/omega-http-core/build-release), ces tests sont sautes."""
from __future__ import annotations

import json
import os
import socket
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend

RATE_LIMITED = {"waf": {"enabled": True, "mode": "block",
                        "rate_limit": {"enabled": True, "global": {"requests": 4, "window_seconds": 60}}}}


def _state(project: ProxyProject) -> dict:
    return json.loads((project.root / "var" / "run" / "engine-state.json").read_text())


def _wait_state_refresh() -> None:
    time.sleep(3.2)  # HEALTH environ 1 fois/s, etat du moteur ecrit toutes les 2 s


def _fd_count(pid: int) -> int:
    return len(os.listdir(f"/proc/{pid}/fd"))


def _read_responses(sock: socket.socket, count: int) -> list[bytes]:
    """`count` reponses lues sur une connexion keep-alive (Content-Length obligatoire)."""
    data = b""
    responses: list[bytes] = []
    while len(responses) < count:
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(65536)
            if not chunk:
                return responses
            data += chunk
        head, data = data.split(b"\r\n\r\n", 1)
        length = 0
        for line in head.split(b"\r\n")[1:]:
            name, _, value = line.partition(b":")
            if name.strip().lower() == b"content-length":
                length = int(value.strip())
        while len(data) < length:
            data += sock.recv(65536)
        responses.append(head + b"\r\n\r\n" + data[:length])
        data = data[length:]
    return responses


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestSingleRateLimitAuthority(unittest.TestCase):
    """D12 : 4 requetes par minute, melange statique / proxy depuis la meme adresse, sur des connexions separees."""

    def _statuses(self, engine: str, proxy: dict | None = None) -> list[int]:
        backend = ScriptedBackend()
        project = ProxyProject(engine, backend.port, options=json.loads(json.dumps(RATE_LIMITED)), proxy=proxy)
        try:
            project.start()
            self.assertEqual(project.effective_engine(), engine)
            address = project.next_address()
            return [project.request("GET", path, address=address)[0]
                    for path in ("/", "/api/ok", "/", "/api/ok", "/", "/api/ok")]
        finally:
            project.stop()
            backend.stop()

    def test_one_bucket_in_every_engine(self):
        expected = [200, 200, 200, 200, 429, 429]
        self.assertEqual(self._statuses("python"), expected, "moteur Python")
        self.assertEqual(self._statuses("native", {"engine": "python"}), expected, "natif, zone confiee a Python")
        self.assertEqual(self._statuses("native"), expected, "natif, auto (zone relayee depuis le lot 11)")
        self.assertEqual(self._statuses("native", {"engine": "native"}), expected, "natif, zone relayee")


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestConnectionGivenBack(unittest.TestCase):
    """HANDOFF_DONE : zone confiee a Python (engine = python ; auto jusqu'au lot 11), connexion rendue apres chaque
    reponse."""

    @classmethod
    def setUpClass(cls):
        cls.backend = ScriptedBackend()
        cls.project = ProxyProject("native", cls.backend.port, proxy={"engine": "python"})
        cls.project.start()

    @classmethod
    def tearDownClass(cls):
        cls.project.stop()
        cls.backend.stop()

    def _keepalive(self, targets: list[str]) -> list[bytes]:
        raw = "".join(f"GET {target} HTTP/1.1\r\nHost: localhost\r\n\r\n" for target in targets).encode()
        with socket.create_connection(("127.0.0.1", self.project.port), timeout=5) as sock:
            sock.sendall(raw)
            return _read_responses(sock, len(targets))

    def test_next_request_is_served_by_the_native_engine(self):
        _wait_state_refresh()
        before = _state(self.project)["requests"]
        for _ in range(5):
            responses = self._keepalive(["/api/ok", "/"])
            self.assertEqual([r.split(b" ", 2)[1] for r in responses], [b"200", b"200"])
            self.assertIn(b"site local", responses[1])
        _wait_state_refresh()
        # Les 5 requetes statiques, venues apres la requete confiee sur la meme connexion, servies par le natif.
        self.assertEqual(_state(self.project)["requests"] - before, 5)

    def test_pipelined_requests_survive_the_return(self):
        # Octets deja lus par Python (requetes suivantes envoyees d'un bloc) rendus avec la connexion.
        responses = self._keepalive(["/api/ok", "/", "/api/ok", "/"])
        self.assertEqual([r.split(b" ", 2)[1] for r in responses], [b"200"] * 4)

    def test_descriptors_stay_stable(self):
        state = _state(self.project)
        pids = (int(state["native_pid"]), int(state["extra"]["security_pid"]))
        self._keepalive(["/api/ok", "/"])  # premier passage : tout ce qui s'ouvre une fois (pool, journaux)
        before = [_fd_count(pid) for pid in pids]
        for _ in range(30):
            self._keepalive(["/api/ok", "/", "/api/ok"])
        time.sleep(0.5)
        self.assertEqual([_fd_count(pid) for pid in pids], before)


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeRelayResources(unittest.TestCase):
    """Relais natif : budgets (C2, S16), descripteurs, aucun octet avant le verdict (S22)."""

    def _project(self, proxy: dict, options: dict | None = None, zone: dict | None = None) -> ProxyProject:
        backend = ScriptedBackend()
        self.addCleanup(backend.stop)
        project = ProxyProject("native", backend.port, options=options, zone=zone, proxy={"engine": "native", **proxy})
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), "native")
        self.backend = backend
        return project

    def test_pending_body_budget_gives_503(self):
        project = self._project({"max_pending_body_mb": 10})
        ok = project.request("POST", "/api/echo", body=b"x" * 1000)[0]
        self.assertEqual(ok, 200)
        # Un seul corps de 10 Mo tient ; deux envois simultanes de 6 Mo depassent le budget de 10 Mo.
        first = socket.create_connection(("127.0.0.1", project.port), timeout=5)
        second = socket.create_connection(("127.0.0.1", project.port), timeout=5)
        try:
            head = f"POST /api/echo HTTP/1.1\r\nHost: localhost\r\nContent-Length: {6 << 20}\r\n\r\n".encode()
            first.sendall(head + b"a" * 1000)
            time.sleep(0.3)  # premier corps en cours de reception : 6 Mo reserves
            second.sendall(head)  # 503 immediat, avant la lecture du corps
            self.assertTrue(second.recv(65536).startswith(b"HTTP/1.1 503 "))
        finally:
            first.close()
            second.close()
        time.sleep(0.2)
        errors = (project.root / "var" / "log" / "error.log").read_text()
        self.assertIn("max_pending_body_mb", errors)
        _wait_state_refresh()
        self.assertEqual(int(_state(project)["extra"]["proxy_pending_body"]), 0)

    def test_blocked_request_never_reaches_the_backend(self):
        project = self._project({}, options={"waf": {"enabled": True, "mode": "block"}})
        status = project.request("GET", "/api/ok?id=1%20union%20select%20password%20from%20users")[0]
        self.assertEqual(status, 403)
        self.assertEqual(self.backend.hits_for("/api/ok"), 0)
        self.assertEqual(project.request("GET", "/api/ok")[0], 200)
        self.assertEqual(self.backend.hits_for("/api/ok"), 1)

    def test_chunked_and_close_framings_are_relayed(self):
        # Lot 4 : 502 et ligne « lot 5 » dans error.log. Lot 5 : relayees en flux (Q4, S13).
        project = self._project({})
        offsets = project.log_offsets()
        self.assertEqual(project.request("GET", "/api/chunked")[0], 200)
        self.assertEqual(project.request("GET", "/api/close")[0], 200)
        self.assertEqual([line for line in project.new_lines("error", offsets) if "lot 5" in line], [])

    def test_descriptors_and_budgets_after_many_relays(self):
        project = self._project({}, zone={"read_timeout_seconds": 1})
        native_pid = int(_state(project)["native_pid"])
        targets = ("/api/ok", "/api/echo", "/api/404", "/api/chunked", "/api/close")
        for target in (*targets, "/api/slow"):  # premier passage : journaux ouverts une fois pour toutes
            project.request("GET", target)
        _wait_state_refresh()
        before = _fd_count(native_pid) - int(_state(project)["extra"]["upstream_idle"])
        for index in range(40):
            project.request("GET", targets[index % len(targets)])
        project.request("GET", "/api/slow")  # 504
        _wait_state_refresh()
        extra = _state(project)["extra"]
        # Lot 5 : les connexions inactives du pool (S14) sont les seuls descripteurs en plus, et les seules reservations.
        self.assertEqual(_fd_count(native_pid) - int(extra["upstream_idle"]), before)
        self.assertGreaterEqual(int(extra["proxy_relayed"]), 30)
        self.assertEqual((extra["proxy_pending_body"], extra["proxy_inspections"]), ("0", "0"))
        self.assertEqual(extra["upstream_connections"], extra["upstream_idle"])


if __name__ == "__main__":
    unittest.main()
