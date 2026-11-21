# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 7 : rechargement, generations et arret propre (C13, C14).

Decisions de l'auteur (2026-11-13) :
- une connexion gardee ouverte prend la configuration EN COURS des sa requete suivante, comme le moteur Python ; la
  requete deja commencee finit avec l'ancienne ;
- a l'arret, une connexion qui attend sa prochaine requete est fermee tout de suite (comme nginx), dans les deux
  moteurs ; seules les requetes en cours ont le delai de grace.

Rechargement teste pendant une reponse longue, un envoi lent et un controle de securite en attente ; pool : les
connexions inactives d'un backend retire sont fermees. Le binaire n'est pas versionne : sans build, ces tests sont
sautes."""
from __future__ import annotations

import json
import os
import signal
import socket
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend, Streamed


def _named(name: str) -> bytes:
    body = name.encode()
    return b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def _long_stream(conn: socket.socket, _head: bytes) -> bool:
    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n")
    for index in range(6):
        conn.sendall(b"6\r\nbloc-%d\r\n" % index)
        time.sleep(0.5)
    conn.sendall(b"0\r\n\r\n")
    return True


def _dechunk(body: bytes) -> tuple[bytes, bool]:
    decoded, position = bytearray(), 0
    while True:
        end = body.find(b"\r\n", position)
        if end < 0:
            return bytes(decoded), False
        size = int(body[position:end], 16)
        if size == 0:
            return bytes(decoded), True
        decoded += body[end + 2:end + 2 + size]
        position = end + 4 + size


def _read_response(sock: socket.socket, buffer: bytearray) -> tuple[bytes, dict[str, str], bytes]:
    while b"\r\n\r\n" not in buffer:
        data = sock.recv(65536)
        if not data:
            raise ConnectionError("connexion fermee")
        buffer += data
    head, _, rest = bytes(buffer).partition(b"\r\n\r\n")
    buffer[:] = rest
    lines = head.split(b"\r\n")
    headers = {k.strip().lower().decode(): v.strip().decode() for k, _, v in (line.partition(b":") for line in lines[1:])}
    if headers.get("transfer-encoding") == "chunked":
        while b"0\r\n\r\n" not in buffer:
            buffer += sock.recv(65536)
        end = bytes(buffer).index(b"0\r\n\r\n") + 5
        body = _dechunk(bytes(buffer[:end]))[0]
        del buffer[:end]
        return lines[0], headers, body
    length = int(headers.get("content-length", "0"))
    while len(buffer) < length:
        buffer += sock.recv(65536)
    body = bytes(buffer[:length])
    del buffer[:length]
    return lines[0], headers, body


class _Reloading:
    project: ProxyProject

    def _config(self) -> dict:
        return json.loads((self.project.root / "config" / "omega-serve.json").read_text())

    def _reload(self, change) -> None:  # type: ignore[no-untyped-def]
        config = self._config()
        change(config)
        (self.project.root / "config" / "omega-serve.json").write_text(json.dumps(config, indent=2))
        state_path = self.project.root / "var" / "run" / "engine-state.json"
        before = json.loads(state_path.read_text()).get("generation", 0)
        assert self.project.process is not None
        self.project.process.send_signal(signal.SIGHUP)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and json.loads(state_path.read_text()).get("generation", 0) == before:
            time.sleep(0.1)
        self.assertGreater(json.loads(state_path.read_text()).get("generation", 0), before)  # type: ignore[attr-defined]


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestReloadDuringTraffic(_Reloading, unittest.TestCase):
    def setUp(self):
        self.first = ScriptedBackend({"/api/qui": _named("premier"), "/api/long": Streamed(_long_stream)})
        self.second = ScriptedBackend({"/api/qui": _named("second")})
        for backend in (self.first, self.second):
            self.addCleanup(backend.stop)
        self.project = ProxyProject("native", self.first.port, proxy={"engine": "native"},
                                    zone={"read_timeout_seconds": 2})
        self.addCleanup(self.project.stop)
        self.project.start()
        self.assertEqual(self.project.effective_engine(), "native")

    def _point_to_second(self, config: dict) -> None:
        config["options"]["reverse_proxy"]["zones"][0]["upstreams"] = [{"host": "127.0.0.1", "port": self.second.port}]

    def test_long_response_survives_a_reload_and_the_next_request_takes_the_new_configuration(self):
        sock = socket.create_connection(("127.0.0.1", self.project.port), timeout=10)
        self.addCleanup(sock.close)
        address = self.project.next_address()
        sock.sendall(f"GET /api/long HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\n\r\n".encode())
        time.sleep(0.6)  # reponse commencee
        self._reload(self._point_to_second)
        buffer = bytearray()
        line, _headers, body = _read_response(sock, buffer)
        self.assertEqual((line, body), (b"HTTP/1.1 200 OK", b"".join(b"bloc-%d" % i for i in range(6))))
        # Meme connexion, requete suivante : nouvelle configuration (decision de l'auteur du 2026-11-13).
        sock.sendall(f"GET /api/qui HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\n\r\n".encode())
        self.assertEqual(_read_response(sock, buffer)[2], b"second")

    def test_slow_upload_survives_a_reload(self):
        sock = socket.create_connection(("127.0.0.1", self.project.port), timeout=10)
        self.addCleanup(sock.close)
        body = b"x=" + b"a" * 4000
        sock.sendall(f"POST /api/echo HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {self.project.next_address()}\r\n"
                     f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body[:1000])
        time.sleep(0.3)
        self._reload(self._point_to_second)
        sock.sendall(body[1000:])
        line, _headers, echoed = _read_response(sock, bytearray())
        self.assertEqual(line, b"HTTP/1.1 200 OK")
        self.assertIn(b"POST /api/echo", echoed)  # requete commencee : ancienne configuration, premier backend
        self.assertEqual(self.first.hits_for("/api/echo"), 1)

    def test_idle_pool_connection_of_a_removed_backend_is_closed(self):
        self.assertEqual(self.project.request("GET", "/api/qui")[2], b"premier")
        time.sleep(3.2)
        state = json.loads((self.project.root / "var" / "run" / "engine-state.json").read_text())
        self.assertEqual(int(state["extra"]["upstream_idle"]), 1)  # connexion gardee au pool
        self._reload(self._point_to_second)
        time.sleep(3.5)
        state = json.loads((self.project.root / "var" / "run" / "engine-state.json").read_text())
        self.assertEqual((state["extra"]["upstream_idle"], state["extra"]["upstream_connections"]), ("0", "0"))
        self.assertEqual(self.project.request("GET", "/api/qui")[2], b"second")


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestReloadWithPendingInspection(_Reloading, unittest.TestCase):
    def test_verdict_still_applies_after_a_reload(self):
        backend = ScriptedBackend({"/api/qui": _named("controle")})
        self.addCleanup(backend.stop)
        self.project = ProxyProject("native", backend.port, proxy={"engine": "native"},
                                    options={"waf": {"enabled": True, "mode": "block"}})
        self.addCleanup(self.project.stop)
        self.project.start()
        state = json.loads((self.project.root / "var" / "run" / "engine-state.json").read_text())
        security_pid = int(state["extra"]["security_pid"])
        os.kill(security_pid, signal.SIGSTOP)  # controle suspendu : l'attaque attend son verdict
        self.addCleanup(lambda: os.kill(security_pid, signal.SIGCONT))
        sock = socket.create_connection(("127.0.0.1", self.project.port), timeout=15)
        self.addCleanup(sock.close)
        sock.sendall(f"GET /api/qui?id=1%20union%20select%20password%20from%20users HTTP/1.1\r\nHost: localhost\r\n"
                     f"X-Forwarded-For: {self.project.next_address()}\r\nConnection: close\r\n\r\n".encode())
        time.sleep(0.5)
        self._reload(lambda config: config["server"].update(keepalive_timeout_seconds=7))
        os.kill(security_pid, signal.SIGCONT)
        line = _read_response(sock, bytearray())[0]
        self.assertTrue(line.startswith(b"HTTP/1.1 403 "), line)  # verdict applique, jamais relaye sans lui
        self.assertEqual(backend.hits_for("/api/qui"), 0)


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestGracefulStop(unittest.TestCase):
    def _project(self, engine: str) -> tuple[ProxyProject, ScriptedBackend]:
        backend = ScriptedBackend({"/api/long": Streamed(_long_stream)})
        self.addCleanup(backend.stop)
        # Delai keep-alive long : sans la fermeture immediate, l'arret attendrait tout le delai de grace (10 s).
        project = ProxyProject(engine, backend.port, zone={"read_timeout_seconds": 2},
                               server={"keepalive_timeout_seconds": 30},
                               proxy={"engine": "native"} if engine == "native" else None)
        self.addCleanup(project.stop)
        project.start()
        return project, backend

    def _stop_time(self, project: ProxyProject) -> float:
        assert project.process is not None
        started = time.monotonic()
        project.process.send_signal(signal.SIGTERM)
        project.process.wait(30)
        return time.monotonic() - started

    def test_idle_keepalive_connection_never_delays_the_stop(self):
        for engine in ("python", "native"):
            with self.subTest(engine=engine):
                project, _backend = self._project(engine)
                sock = socket.create_connection(("127.0.0.1", project.port), timeout=10)
                self.addCleanup(sock.close)
                sock.sendall(f"GET / HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {project.next_address()}\r\n\r\n"
                             .encode())
                _read_response(sock, bytearray())  # connexion gardee ouverte, plus rien a faire
                self.assertLess(self._stop_time(project), 5.0)  # delai de grace : 10 s par defaut
                self.assertEqual(sock.recv(10), b"")  # fermee par le serveur
                errors = (project.root / "var" / "log" / "error.log")
                self.assertNotIn("arret force", errors.read_text() if errors.exists() else "")

    def test_request_head_already_started_gets_the_grace_period(self):
        # Seule une connexion qui n'a RIEN recu de sa requete est fermee tout de suite : une tete commencee (ligne de
        # requete lue, en-tetes pas finis) a le delai de grace, dans les deux moteurs (regression trouvee par la suite
        # complete du lot 7 : le moteur Python la fermait).
        for engine in ("python", "native"):
            with self.subTest(engine=engine):
                project, _backend = self._project(engine)
                sock = socket.create_connection(("127.0.0.1", project.port), timeout=10)
                self.addCleanup(sock.close)
                sock.sendall(f"GET / HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {project.next_address()}\r\n"
                             .encode())
                time.sleep(0.3)
                assert project.process is not None
                project.process.send_signal(signal.SIGTERM)
                time.sleep(1.0)
                self.assertIsNone(project.process.poll())  # attend la fin de la requete commencee
                sock.sendall(b"\r\n")
                line = _read_response(sock, bytearray())[0]
                self.assertEqual(line, b"HTTP/1.1 200 OK")
                project.process.wait(30)

    def test_response_in_progress_finishes_before_the_stop(self):
        for engine in ("python", "native"):
            with self.subTest(engine=engine):
                project, _backend = self._project(engine)
                sock = socket.create_connection(("127.0.0.1", project.port), timeout=10)
                self.addCleanup(sock.close)
                sock.sendall(f"GET /api/long HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {project.next_address()}"
                             "\r\n\r\n".encode())
                time.sleep(0.6)
                assert project.process is not None
                project.process.send_signal(signal.SIGTERM)
                _line, _headers, body = _read_response(sock, bytearray())
                self.assertEqual(body, b"".join(b"bloc-%d" % i for i in range(6)))  # rien de coupe
                self.assertEqual(sock.recv(10), b"")  # puis fermee : plus de keep-alive pendant l'arret
                project.process.wait(30)
                with self.assertRaises(OSError):  # plus aucune connexion acceptee
                    socket.create_connection(("127.0.0.1", project.port), timeout=2).close()


if __name__ == "__main__":
    unittest.main()
