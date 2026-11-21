# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 9 : TLS direct pour les zones natives (C16), de bout en bout, dans les deux moteurs.

Avant le lot 9, `options.reverse_proxy.engine = native` avec `tls.mode = direct` etait refuse (P7) : la zone ne
pouvait pas etre relayee par le natif. Depuis, le natif chiffre lui-meme vers le client (meme contexte TLS que le
statique) et relaie la zone : requete, corps, reponse en flux et contre-pression passent par la couche TLS.

- `X-Forwarded-Proto: https` vers le backend, dans les deux moteurs ;
- keep-alive qui melange zone et statique sur une meme connexion TLS ;
- reponse longue lue lentement (SSL_write partiel, reprise par EPOLLOUT) ; reponse chunked en plusieurs fois ;
- client parti au milieu d'une reponse : ligne d'access.log, serveur intact ;
- /.omega-serv-admin/ toujours servi par le processus de securite n° 0, en TLS aussi (P6) : la session TLS suit la
  connexion jusqu'au fil 0.

Poignees de main comptees dans la capacite (S19, D30) : fait au lot A (test_max_connections).
Le binaire n'est pas versionne : sans build, ces tests sont sautes."""
from __future__ import annotations

import hashlib
import os
import select
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.native_engine import NativeEngine
from tests.integration.proxy_harness import (
    NATIVE_BINARY,
    ProxyProject,
    ScriptedBackend,
    Streamed,
    parse_response,
)

ENGINES = ("python", "native")
ADMIN = b"/.omega-serv-admin/"


def _client_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _read_all(sock: socket.socket) -> bytes:
    chunks = []
    while True:
        try:
            data = sock.recv(65536)
        except (TimeoutError, ConnectionResetError, ssl.SSLError):
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


def _read_response(sock: socket.socket, buffer: bytearray) -> tuple[int, dict[str, list[str]], bytes]:
    """Une reponse a Content-Length sur une connexion gardee ; `buffer` garde ce qui suit."""
    while b"\r\n\r\n" not in buffer:
        data = sock.recv(65536)
        if not data:
            raise ConnectionError("connexion fermee avant la tete")
        buffer += data
    head_end = buffer.index(b"\r\n\r\n") + 4
    status, headers, _ = parse_response(bytes(buffer[:head_end]))
    length = int(headers.get("content-length", ["0"])[0])
    while len(buffer) < head_end + length:
        data = sock.recv(65536)
        if not data:
            raise ConnectionError("connexion fermee avant la fin du corps")
        buffer += data
    body = bytes(buffer[head_end:head_end + length])
    del buffer[:head_end + length]
    return status, headers, body


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeZoneUnderDirectTls(unittest.TestCase):
    def _backend(self, scripts: dict | None = None) -> ScriptedBackend:
        backend = ScriptedBackend(scripts)
        self.addCleanup(backend.stop)
        return backend

    def _project(self, engine: str, backend: ScriptedBackend, zone: dict | None = None) -> ProxyProject:
        project = ProxyProject(engine, backend.port, zone={"read_timeout_seconds": 5, **(zone or {})},
                               proxy={"engine": "native"} if engine == "native" else None, client_tls=True)
        self.addCleanup(project.stop)
        project.start()
        # Avant le lot 9 : engine = native refuse avec TLS direct - le serveur ne demarre pas en natif.
        self.assertEqual(project.effective_engine(), engine)
        return project

    def test_zone_is_relayed_over_tls_with_forwarded_proto_https(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend)
                status, headers, body, _raw = project.request("GET", "/api/ok")
                self.assertEqual((status, body), (200, b"reponse-b"))
                self.assertEqual(headers.get("x-omega-cache"), ["BYPASS"])
                head = backend.requests_for("/api/ok")[-1].decode("latin-1").lower()
                self.assertIn("x-forwarded-proto: https\r\n", head)  # protocole reel de la connexion
                self.assertIn(f"x-forwarded-port: {project.port}\r\n", head)

    def test_request_body_crosses_tls(self):
        payload = os.urandom(300 * 1024)  # plusieurs enregistrements TLS : lecture du corps jusqu'a want_read
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend)
                status, _headers, _body, _raw = project.request("POST", "/api/ok", body=payload, timeout=10)
                self.assertEqual(status, 200)
                head = backend.requests_for("/api/ok")[-1].decode("latin-1").lower()
                self.assertIn(f"content-length: {len(payload)}\r\n", head)

    def test_keep_alive_mixes_zone_and_static_on_one_tls_connection(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend)
                with project.connect(timeout=10) as sock:
                    buffer = bytearray()
                    seen = []
                    for target in ("/api/ok", "/index.html", "/api/echo", "/api/ok"):
                        sock.sendall(f"GET {target} HTTP/1.1\r\nHost: localhost\r\n"
                                     f"X-Forwarded-For: {project.next_address()}\r\n\r\n".encode())
                        status, _headers, body = _read_response(sock, buffer)
                        seen.append((status, body[:9]))
                self.assertEqual(seen, [(200, b"reponse-b"), (200, b"site loca"), (200, b"GET /api/"),
                                        (200, b"reponse-b")])

    def test_pipelined_requests_over_tls_are_answered_in_order(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend)
                address = project.next_address()
                raw = "".join(f"GET {t} HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\n\r\n"
                              for t in ("/api/ok", "/api/echo"))
                raw += f"GET /api/ok HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\nConnection: close\r\n\r\n"
                with project.connect(timeout=10) as sock:
                    sock.sendall(raw.encode())  # un seul enregistrement TLS : tout est dechiffre d'un coup
                    data = bytearray(_read_all(sock))
                statuses = []
                while data:
                    status, _headers, _body = _read_response(_NoSocket(), data)
                    statuses.append(status)
                self.assertEqual(statuses, [200, 200, 200])

    def test_long_response_read_slowly_arrives_whole(self):
        payload = os.urandom(4 * 1024 * 1024)  # SSL_write partiel, contre-pression du relais, reprise par EPOLLOUT

        def big(conn: socket.socket, _head: bytes) -> bool:
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: "
                         + str(len(payload)).encode() + b"\r\n\r\n")
            for offset in range(0, len(payload), 65536):
                conn.sendall(payload[offset:offset + 65536])
            return True

        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend({"/api/gros": Streamed(big)})
                project = self._project(engine, backend)
                raw_sock = socket.create_connection(("127.0.0.1", project.port), timeout=20)
                raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16384)
                sock = _client_context().wrap_socket(raw_sock, server_hostname="localhost")
                self.addCleanup(sock.close)
                sock.sendall(f"GET /api/gros HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {project.next_address()}"
                             "\r\nConnection: close\r\n\r\n".encode())
                received = bytearray()
                while True:
                    try:
                        data = sock.recv(16384)
                    except ssl.SSLError:
                        break
                    if not data:
                        break
                    received += data
                    if len(received) < 1024 * 1024:
                        time.sleep(0.002)  # client lent au debut : le relais suspend puis reprend
                head, _, body = bytes(received).partition(b"\r\n\r\n")
                self.assertTrue(head.startswith(b"HTTP/1.1 200 "), head[:40])
                self.assertEqual(len(body), len(payload))
                self.assertEqual(hashlib.sha256(body).digest(), hashlib.sha256(payload).digest())

    def test_chunked_response_in_several_writes(self):
        def chunks(conn: socket.socket, _head: bytes) -> bool:
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n")
            for piece in (b"un-", b"deux-", b"trois"):
                conn.sendall(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
                time.sleep(0.1)
            conn.sendall(b"0\r\n\r\n")
            return True

        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend({"/api/flux": Streamed(chunks)})
                project = self._project(engine, backend)
                status, headers, body, _raw = project.request("GET", "/api/flux")
                self.assertEqual(status, 200)
                if headers.get("transfer-encoding") == ["chunked"]:  # natif : en flux ; Python : corps entier
                    body = b"".join(part for part in body.split(b"\r\n")[1::2])
                self.assertEqual(body, b"un-deux-trois")

    def test_client_leaving_mid_response_is_logged_and_server_keeps_serving(self):
        payload = b"x" * (8 * 1024 * 1024)

        def big(conn: socket.socket, _head: bytes) -> bool:
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: "
                         + str(len(payload)).encode() + b"\r\n\r\n")
            try:
                for offset in range(0, len(payload), 65536):
                    conn.sendall(payload[offset:offset + 65536])
            except OSError:
                return False
            return True

        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend({"/api/gros": Streamed(big)})
                project = self._project(engine, backend)
                offsets = project.log_offsets()
                address = project.next_address()
                sock = project.connect(timeout=10)
                sock.sendall(f"GET /api/gros HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\n"
                             "Connection: close\r\n\r\n".encode())
                sock.recv(65536)  # la tete et un debut de corps sont partis
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")
                sock.close()  # RST : client parti au milieu
                lines = []
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline and not lines:
                    lines = [line for line in project.new_lines("access", offsets, wait=0.2) if address in line]
                self.assertEqual(len(lines), 1, lines)
                self.assertIn('"GET /api/gros HTTP/1.1" 200 ', lines[0])
                self.assertEqual(project.request("GET", "/api/ok")[0], 200)  # serveur intact


class _NoSocket:
    """`_read_response` sur des octets deja tous recus."""

    def recv(self, _size: int) -> bytes:
        return b""


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestAdminOverTlsGoesToFirstSecurityProcess(unittest.TestCase):
    """P6 en TLS direct (lot 9) : avec deux processus de securite, /.omega-serv-admin/ arrive toujours au n° 0, meme
    acceptee par le fil 1. Avant le lot 9, une connexion TLS n'etait jamais deplacee : le n° 1 la servait. Faux
    processus de securite : les deux canaux sont lus ici ; les autres requetes (/.omega-serv-load/, route deleguee au
    processus du fil) montrent quel fil a accepte la connexion."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "var" / "log").mkdir(parents=True)
        certs = self.root / "certs"
        certs.mkdir()
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-keyout", str(certs / "key.pem"), "-out", str(certs / "cert.pem"), "-days", "2",
                        "-subj", "/CN=localhost"], check=True, capture_output=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _burst(self, security_processes: int) -> tuple[dict, int]:
        """(trames INSPECT par (canal, administration ?), reponses 200 recues pour l'administration). Socket d'ecoute
        neuve a chaque rafale : l'arret du natif la ferme (shutdown sur la socket partagee)."""
        listen = socket.create_server(("127.0.0.1", 0), backlog=512)
        port = listen.getsockname()[1]
        config = OmegaServConfig.from_dict({
            "server": {"engine": "native", "port": port, "max_connections": 2000},
            "tls": {"enabled": True, "mode": "direct", "certificate": {
                "certificate_path": str(self.root / "certs" / "cert.pem"),
                "private_key_path": str(self.root / "certs" / "key.pem")}},
            "options": {
                "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"]},
                "reverse_proxy": {"enabled": True, "engine": "native", "zones": [
                    {"url_prefix": "/app/", "upstreams": [{"host": "10.0.0.5", "port": 8080}]}]}}})
        pairs = [ipc.data_channel_pair() for _ in range(2)]
        engine = NativeEngine(NATIVE_BINARY, self.root, threads=2, security_processes=security_processes)
        engine.start(config, [listen.fileno()], [native.fileno() for native, _worker in pairs])
        for native, _worker in pairs:
            native.close()
        ends = [worker for _native, worker in pairs]
        frames: dict[tuple[int, bool], int] = {}
        admin_ok = [0]
        lock = threading.Lock()
        stop = threading.Event()

        def fake_security_processes():
            while not stop.is_set():
                ready, _, _ = select.select(ends, [], [], 0.1)
                for end in ready:
                    try:
                        frame, fd = ipc.recv_frame(end, 0.1)
                    except (TimeoutError, ipc.FrameError):
                        continue
                    if fd is not None:
                        os.close(fd)
                    if frame.type != ipc.INSPECT:
                        continue
                    admin = any(ADMIN in value for _tag, value in frame.fields)
                    with lock:
                        key = (ends.index(end), admin)
                        frames[key] = frames.get(key, 0) + 1
                    ipc.send_frame(end, ipc.verdict_frame(frame.request_id, HttpResponse.empty(HttpStatus.OK), False))

        def client(index: int):
            context = _client_context()
            for n in range(20):
                path = "/.omega-serv-admin/status" if (index + n) % 2 else "/.omega-serv-load/"
                try:
                    with context.wrap_socket(socket.create_connection(("127.0.0.1", port), timeout=5),
                                             server_hostname="localhost") as conn:
                        conn.sendall(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
                        head = conn.recv(64)
                        if path.startswith("/.omega-serv-admin/") and head.startswith(b"HTTP/1.1 200"):
                            with lock:
                                admin_ok[0] += 1
                except OSError:
                    pass

        reader = threading.Thread(target=fake_security_processes)
        reader.start()
        try:
            clients = [threading.Thread(target=client, args=(i,)) for i in range(8)]
            for thread in clients:
                thread.start()
            for thread in clients:
                thread.join()
        finally:
            stop.set()
            reader.join()
            engine.stop(2.0)
            listen.close()
            for end in ends:
                end.close()
        return frames, admin_ok[0]

    def test_admin_over_tls_always_reaches_process_zero(self):
        for _attempt in range(5):
            frames, admin_ok = self._burst(security_processes=2)
            if frames.get((1, False), 0) >= 3:  # le fil 1 a bien accepte des connexions
                break
        else:
            self.skipTest("le fil 1 n'a accepte aucune connexion (machine trop peu chargee)")
        self.assertEqual(frames.get((1, True), 0), 0, frames)
        self.assertEqual(frames.get((0, True), 0), 80, frames)  # 8 clients x 10 requetes d'administration
        self.assertEqual(admin_ok, 80)

    def test_without_second_process_nothing_moves(self):
        for _attempt in range(5):
            frames, admin_ok = self._burst(security_processes=1)
            if frames.get((1, False), 0) >= 3:
                break
        else:
            self.skipTest("le fil 1 n'a accepte aucune connexion (machine trop peu chargee)")
        self.assertGreater(frames.get((1, True), 0), 0, frames)
        self.assertEqual(admin_ok, 80)


if __name__ == "__main__":
    unittest.main()
