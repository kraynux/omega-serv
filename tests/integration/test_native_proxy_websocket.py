# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 10 : tunnel WebSocket (C17), de bout en bout, dans les deux moteurs.

Avant le lot 10, une zone `websocket_enabled` etait confiee a Python (ZONE_WEBSOCKET) : le natif rendait la connexion
et Python faisait le tunnel. Depuis, le natif fait lui-meme la mise a niveau et le tunnel, avec les memes regles :

- requete vers le backend avec `Connection`/`Upgrade` gardes, connexion neuve, aucun nouvel essai ;
- 101 relaye avec les en-tetes du backend, octets envoyes avec le 101 transmis, puis tunnel dans les deux sens ;
- refus du backend : sans corps, `Content-Length: 0`, `Connection: close` (D14) ; backend injoignable : 502 nu ;
- delai d'inactivite de la zone (Q11, `websocket_idle_timeout_seconds`, 0 = aucun) et fin du delai de grace de
  l'arret (C14) : trame 1001 vers le client et vers le backend (decision de l'auteur du 2026-11-14), sauf au milieu
  d'une trame ;
- ligne d'access.log a la fermeture du tunnel : 101 et octets envoyes au client (decision du 2026-11-14, avant 0) ;
- contre-pression : flux de 8 Mio lu lentement, intact ;
- TLS direct : le tunnel natif passe par la couche TLS (avant le lot 10, engine = native etait refuse : zone confiee).

Le binaire n'est pas versionne : sans build, ces tests sont sautes."""
from __future__ import annotations

import base64
import hashlib
import os
import re
import socket
import ssl
import threading
import time
import unittest

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject

ENGINES = ("python", "native")
GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
GOING_AWAY = b"\x88\x02\x03\xe9"


def encode_frame(opcode: int, payload: bytes, masked: bool) -> bytes:
    head = bytes((0x80 | opcode,))
    mask_bit = 0x80 if masked else 0
    if len(payload) < 126:
        head += bytes((mask_bit | len(payload),))
    elif len(payload) < 65536:
        head += bytes((mask_bit | 126,)) + len(payload).to_bytes(2, "big")
    else:
        head += bytes((mask_bit | 127,)) + len(payload).to_bytes(8, "big")
    if not masked:
        return head + payload
    mask = os.urandom(4)
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class FrameReader:
    """Trames lues d'une socket (masquees ou non) ; `buffer` garde ce qui suit."""

    def __init__(self, sock: socket.socket, buffer: bytes = b"") -> None:
        self.sock = sock
        self.buffer = bytearray(buffer)
        self.eof = False

    def _fill(self, size: int) -> bool:
        while len(self.buffer) < size:
            try:
                data = self.sock.recv(65536)
            except (TimeoutError, ConnectionResetError, ssl.SSLError, OSError):
                data = b""
            if not data:
                self.eof = True
                return False
            self.buffer += data
        return True

    def read(self) -> tuple[int, bytes] | None:
        if not self._fill(2):
            return None
        length = self.buffer[1] & 0x7F
        masked = bool(self.buffer[1] & 0x80)
        offset = 2
        if length == 126:
            if not self._fill(4):
                return None
            length, offset = int.from_bytes(self.buffer[2:4], "big"), 4
        elif length == 127:
            if not self._fill(10):
                return None
            length, offset = int.from_bytes(self.buffer[2:10], "big"), 10
        mask = b""
        if masked:
            if not self._fill(offset + 4):
                return None
            mask, offset = bytes(self.buffer[offset:offset + 4]), offset + 4
        if not self._fill(offset + length):
            return None
        payload = bytes(self.buffer[offset:offset + length])
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        opcode = self.buffer[0] & 0x0F
        del self.buffer[:offset + length]
        return opcode, payload


class WebSocketBackend:
    """Faux backend WebSocket : 101 (Sec-WebSocket-Accept calcule), puis echo des messages. Messages speciaux :
    `big:N` (N octets en trames de 64 Kio), `partial` (trame annoncee a 100 octets, 10 envoyes seulement), `bye`
    (le backend ferme sa socket). `refuse` : reponse ecrite telle quelle a la place du 101. `with_101` : octets
    envoyes dans la meme ecriture que le 101."""

    def __init__(self, refuse: bytes | None = None, with_101: bytes = b"") -> None:
        self.refuse = refuse
        self.with_101 = with_101
        self.heads: list[bytes] = []
        self.close_frames: list[bytes] = []  # charge utile des trames de fermeture recues (demasquee)
        self.unmasked_frames = 0              # RFC 6455 §5.1 : un client masque toujours
        self.ended = threading.Event()
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def stop(self) -> None:
        try:
            self._listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._listener.close()

    def _accept(self) -> None:
        while True:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        with conn:
            buffer = b""
            while b"\r\n\r\n" not in buffer:
                data = conn.recv(65536)
                if not data:
                    return
                buffer += data
            head, rest = buffer.split(b"\r\n\r\n", 1)
            self.heads.append(head + b"\r\n\r\n")
            if self.refuse is not None:
                conn.sendall(self.refuse)
                return
            key = b""
            for line in head.split(b"\r\n")[1:]:
                name, _, value = line.partition(b":")
                if name.strip().lower() == b"sec-websocket-key":
                    key = value.strip()
            accept = base64.b64encode(hashlib.sha1(key + GUID).digest())
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                         b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n" + self.with_101)
            reader = FrameReader(conn, rest)
            try:
                while True:
                    if len(reader.buffer) >= 2 and not reader.buffer[1] & 0x80:
                        self.unmasked_frames += 1
                    frame = reader.read()
                    if frame is None:
                        break
                    opcode, payload = frame
                    if opcode == 0x8:
                        self.close_frames.append(payload)
                        conn.sendall(encode_frame(0x8, payload[:2], masked=False))
                        break
                    if payload.startswith(b"big:"):
                        total = int(payload[4:])
                        block = os.urandom(65536)
                        sent = 0
                        while sent < total:
                            piece = block[:min(65536, total - sent)]
                            conn.sendall(encode_frame(0x2, piece, masked=False))
                            sent += len(piece)
                    elif payload == b"partial":
                        conn.sendall(b"\x82\x64" + b"0123456789")  # 100 octets annonces, 10 envoyes
                    elif payload == b"bye":
                        conn.sendall(encode_frame(0x1, b"au revoir", masked=False))
                        break
                    else:
                        conn.sendall(encode_frame(opcode, b"echo:" + payload, masked=False))
            except OSError:
                pass
            finally:
                self.ended.set()


def upgrade_request(address: str, path: str = "/api/ws") -> bytes:
    return (f"GET {path} HTTP/1.1\r\nHost: site.example\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n"
            f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n"
            f"X-Forwarded-For: {address}\r\n\r\n").encode()


def read_head(sock: socket.socket) -> tuple[bytes, bytes]:
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        data = sock.recv(65536)
        if not data:
            return buffer, b""
        buffer += data
    head, rest = buffer.split(b"\r\n\r\n", 1)
    return head + b"\r\n\r\n", rest


def read_until_closed(sock: socket.socket, timeout: float) -> bytes:
    sock.settimeout(timeout)
    chunks = []
    while True:
        try:
            data = sock.recv(65536)
        except (TimeoutError, ConnectionResetError, ssl.SSLError, OSError):
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestWebSocketTunnel(unittest.TestCase):
    def _backend(self, **kwargs) -> WebSocketBackend:
        backend = WebSocketBackend(**kwargs)
        self.addCleanup(backend.stop)
        return backend

    def _project(self, engine: str, port: int, zone: dict | None = None, server: dict | None = None,
                 client_tls: bool = False) -> ProxyProject:
        project = ProxyProject(engine, port, zone={"websocket_enabled": True, "read_timeout_seconds": 3, **(zone or {})},
                               server=server, proxy={"engine": "native"} if engine == "native" else None,
                               client_tls=client_tls)
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), engine)
        return project

    def _open(self, project: ProxyProject) -> tuple[socket.socket, bytes, FrameReader]:
        sock = project.connect(timeout=10)
        self.addCleanup(sock.close)
        sock.sendall(upgrade_request(project.next_address()))
        head, rest = read_head(sock)
        return sock, head, FrameReader(sock, rest)

    @staticmethod
    def _access_size(project: ProxyProject, offsets: dict[str, int], status: int, wait: float = 0.6) -> int | None:
        for line in project.new_lines("access", offsets, wait=wait):
            match = re.search(rf'"GET /api/ws HTTP/1.1" {status} (\d+|-)', line)
            if match:
                return 0 if match.group(1) == "-" else int(match.group(1))
        return None

    def test_upgrade_echo_and_access_line_with_bytes_sent(self):
        heads = {}
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port)
                offsets = project.log_offsets()
                sock, head, reader = self._open(project)
                self.assertTrue(head.startswith(b"HTTP/1.1 101 Switching Protocols\r\n"), head[:60])
                self.assertIn(b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n", head)
                heads[engine] = head
                for message in (b"bonjour", b"x" * 200, b"y" * 70000):
                    sock.sendall(encode_frame(0x2, message, masked=True))
                    self.assertEqual(reader.read(), (0x2, b"echo:" + message))
                sock.sendall(encode_frame(0x8, b"\x03\xe8", masked=True))
                self.assertEqual(reader.read(), (0x8, b"\x03\xe8"))
                sock.close()
                sent = backend.heads[-1].decode("latin-1").lower()
                self.assertIn("connection: upgrade\r\n", sent)
                self.assertIn("upgrade: websocket\r\n", sent)
                self.assertIn("sec-websocket-key: dghlihnhbxbszsbub25jzq==\r\n", sent)
                self.assertIn("x-omega-proxy-hops: 1\r\n", sent)
                self.assertEqual(backend.unmasked_frames, 0)
                expected = sum(len(encode_frame(0x2, b"echo:" + m, masked=False))
                               for m in (b"bonjour", b"x" * 200, b"y" * 70000)) + 4
                self.assertEqual(self._access_size(project, offsets, 101), expected)
        self.assertEqual(heads["python"], heads["native"])  # C20 : meme tete 101 octet pour octet

    def test_bytes_sent_with_the_101_reach_the_client(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend(with_101=encode_frame(0x1, b"bienvenue", masked=False))
                project = self._project(engine, backend.port)
                _sock, head, reader = self._open(project)
                self.assertIn(b" 101 ", head)
                self.assertEqual(reader.read(), (0x1, b"bienvenue"))

    def test_refused_upgrade_is_answered_without_body_and_closed(self):
        raws = {}
        refusal = (b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: 6\r\nKeep-Alive: 5\r\n\r\n"
                   b"refuse")
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend(refuse=refusal)
                project = self._project(engine, backend.port)
                offsets = project.log_offsets()
                with project.connect(timeout=10) as sock:
                    sock.sendall(upgrade_request(project.next_address()))
                    raw = read_until_closed(sock, 5)
                self.assertEqual(raw, b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: 0\r\n"
                                      b"Connection: close\r\n\r\n")
                raws[engine] = raw
                self.assertEqual(self._access_size(project, offsets, 403), 0)
        self.assertEqual(raws["python"], raws["native"])

    def test_unreachable_backend_gives_a_bare_502(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            dead_port = probe.getsockname()[1]
        for engine in ENGINES:
            with self.subTest(engine=engine):
                project = self._project(engine, dead_port)
                with project.connect(timeout=10) as sock:
                    sock.sendall(upgrade_request(project.next_address()))
                    raw = read_until_closed(sock, 5)
                self.assertEqual(raw, b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")

    def test_idle_timeout_sends_1001_both_ways(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port, zone={"websocket_idle_timeout_seconds": 1})
                offsets = project.log_offsets()
                _sock, _head, reader = self._open(project)
                started = time.monotonic()
                self.assertEqual(reader.read(), (0x8, b"\x03\xe9"))  # 1001, sans masque
                elapsed = time.monotonic() - started
                self.assertGreater(elapsed, 0.7)
                self.assertLess(elapsed, 4)
                self.assertIsNone(reader.read())  # puis fermeture
                self.assertTrue(backend.ended.wait(5))
                self.assertEqual(backend.close_frames, [b"\x03\xe9"])  # masquee, demasquee par le backend
                self.assertEqual(self._access_size(project, offsets, 101), 0)

    def test_activity_in_either_direction_keeps_the_tunnel_open(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port, zone={"websocket_idle_timeout_seconds": 1})
                sock, _head, reader = self._open(project)
                for i in range(6):  # 3 s d'echanges toutes les 0,5 s : jamais 1 s sans octet
                    time.sleep(0.5)
                    sock.sendall(encode_frame(0x1, b"ping %d" % i, masked=True))
                    self.assertEqual(reader.read(), (0x1, b"echo:ping %d" % i))

    def test_zero_idle_timeout_never_closes(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port, zone={"websocket_idle_timeout_seconds": 0})
                sock, _head, reader = self._open(project)
                time.sleep(2.5)
                sock.sendall(encode_frame(0x1, b"encore la", masked=True))
                self.assertEqual(reader.read(), (0x1, b"echo:encore la"))

    def test_no_1001_in_the_middle_of_a_frame(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port, zone={"websocket_idle_timeout_seconds": 1})
                sock, _head, reader = self._open(project)
                sock.sendall(encode_frame(0x1, b"partial", masked=True))
                rest = bytes(reader.buffer) + read_until_closed(sock, 6)
                self.assertEqual(rest, b"\x82\x64" + b"0123456789")  # trame coupee : rien d'insere au milieu
                self.assertTrue(backend.ended.wait(5))
                self.assertEqual(backend.close_frames, [b"\x03\xe9"])  # l'autre sens est entre deux trames

    def test_long_stream_read_slowly_arrives_whole(self):
        total = 8 * 1024 * 1024
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port)
                offsets = project.log_offsets()
                sock, _head, reader = self._open(project)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32 * 1024)
                sock.sendall(encode_frame(0x1, b"big:%d" % total, masked=True))
                received = 0
                wire = 0
                frames = 0
                while received < total:
                    frame = reader.read()
                    self.assertIsNotNone(frame)
                    received += len(frame[1])
                    wire += len(encode_frame(frame[0], frame[1], masked=False))
                    frames += 1
                    if frames % 16 == 0:
                        time.sleep(0.05)  # client lent : la contre-pression suspend la lecture du backend
                self.assertEqual(received, total)
                sock.sendall(encode_frame(0x8, b"\x03\xe8", masked=True))
                reader.read()
                sock.close()
                size = self._access_size(project, offsets, 101, wait=1.0)
                self.assertEqual(size, wire + 4)  # trames recues telles quelles, puis la fermeture renvoyee

    def test_backend_closing_ends_the_tunnel_after_its_last_bytes(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port)
                sock, _head, reader = self._open(project)
                sock.sendall(encode_frame(0x1, b"bye", masked=True))
                self.assertEqual(reader.read(), (0x1, b"au revoir"))
                self.assertIsNone(reader.read())  # backend parti : tunnel ferme, sans 1001

    def test_shutdown_closes_tunnels_with_1001_after_the_grace_period(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port, server={"shutdown_grace_period_seconds": 1})
                offsets = project.log_offsets()
                sock, _head, reader = self._open(project)
                sock.sendall(encode_frame(0x1, b"avant", masked=True))
                self.assertEqual(reader.read(), (0x1, b"echo:avant"))
                assert project.process is not None
                project.process.terminate()
                self.assertEqual(reader.read(), (0x8, b"\x03\xe9"))
                project.process.wait(15)
                self.assertTrue(backend.ended.wait(5))
                self.assertEqual(backend.close_frames, [b"\x03\xe9"])
                self.assertEqual(self._access_size(project, offsets, 101, wait=0.2),
                                 len(encode_frame(0x1, b"echo:avant", masked=False)))  # la 1001 ajoutee n'y est pas

    def test_tunnel_over_direct_tls(self):
        # Avant le lot 10 : zone WebSocket confiee a Python, et engine = native refuse avec TLS direct (P7).
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend()
                project = self._project(engine, backend.port, client_tls=True)
                sock, head, reader = self._open(project)
                self.assertIn(b" 101 ", head)
                for message in (b"chiffre", os.urandom(100_000)):
                    sock.sendall(encode_frame(0x2, message, masked=True))
                    self.assertEqual(reader.read(), (0x2, b"echo:" + message))
                self.assertIn("x-forwarded-proto: https\r\n", backend.heads[-1].decode("latin-1").lower())

    def test_ordinary_requests_of_a_websocket_zone_are_still_relayed(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend(refuse=b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                project = self._project(engine, backend.port)
                # Upgrade sans le jeton dans Connection : requete ordinaire, en-tete de saut retire.
                status, _headers, body, _raw = project.request("GET", "/api/page", headers=["Upgrade: websocket"])
                self.assertEqual((status, body), (200, b"ok"))
                self.assertNotIn(b"upgrade", backend.heads[-1].lower())


if __name__ == "__main__":
    unittest.main()
