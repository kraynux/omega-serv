# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 5 : protocole complet du relais natif (C5), flux et contre-pression (C12), delais (C11),
pool (S14), nouvel essai (C8), budgets (C2), abandon et taille journalisee (P2, P3).

Decisions de l'auteur (2026-11-13) :
- reponse terminee par la fermeture du backend : relayee en chunked a un client HTTP/1.1, qui garde sa connexion ;
- au-dela de max_response_body_mb, cette reponse deja commencee est coupee (memoire bornee), sans bloc final ;
- pool : constantes (10 connexions inactives par backend, reparties entre les fils ; 60 s d'inactivite). Lot 11
  (mesures, 2026-11-14) : 32 par backend et par fil, toutes sous la moitie de max_upstream_connections.

Ecarts voulus avec le moteur Python, qui lit toute la reponse avant de l'envoyer : le natif envoie en chunked ce que
Python envoie avec Content-Length ; une erreur du backend apres l'envoi de la tete coupe la connexion (C4) au lieu
d'un 502. Le binaire n'est pas versionne : sans build, ces tests sont sautes."""
from __future__ import annotations

import hashlib
import json
import socket
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend, Streamed

NATIVE_RELAY = {"engine": "native"}
BIG = 32 << 20
BIG_BODY = (b"0123456789abcdef" * 4096) * (BIG // 65536)
BIG_CHUNKED_PARTS = 256  # 256 blocs de 64 Kio = 16 Mio


def _chunked_head(status: str = "200 OK") -> bytes:
    return f"HTTP/1.1 {status}\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n".encode()


def _stream_slow(conn: socket.socket, _head: bytes) -> bool:
    conn.sendall(_chunked_head() + b"5\r\ndebut\r\n")
    time.sleep(0.8)  # sous read_timeout_seconds (1 s) : le delai vaut entre deux blocs (C11)
    conn.sendall(b"3\r\nfin\r\n0\r\n\r\n")
    return True


def _stall(conn: socket.socket, _head: bytes) -> bool:
    conn.sendall(_chunked_head() + b"5\r\ndebut\r\n")
    time.sleep(3)  # read_timeout_seconds = 1 : le relais coupe avant
    conn.sendall(b"3\r\nfin\r\n0\r\n\r\n")
    return False


def _cut(conn: socket.socket, _head: bytes) -> bool:
    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 1000000\r\n\r\n" + b"c" * 100_000)
    time.sleep(0.2)
    return False  # fermee avant la longueur annoncee


def _big(conn: socket.socket, _head: bytes) -> bool:
    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: "
                 + str(BIG).encode() + b"\r\n\r\n" + BIG_BODY)
    return True


def _big_chunked(conn: socket.socket, _head: bytes) -> bool:
    conn.sendall(_chunked_head())
    block = b"%x\r\n" % 65536 + BIG_BODY[:65536] + b"\r\n"
    for _ in range(BIG_CHUNKED_PARTS):
        conn.sendall(block)
    conn.sendall(b"0\r\n\r\n")
    return True


SCRIPTS = {
    "/api/trailers": _chunked_head() + b"5;ext=1\r\nhello\r\n6\r\n world\r\n0\r\nX-Trailer: secret\r\n\r\n",
    "/api/empty-404": _chunked_head("404 Not Found") + b"0\r\n\r\n",
    "/api/empty-503-close": b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n",
    "/api/close-big": b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n" + b"z" * (3 << 20),
    "/api/stream-slow": Streamed(_stream_slow),
    "/api/stall": Streamed(_stall),
    "/api/cut": Streamed(_cut),
    "/api/big": Streamed(_big),
    "/api/big-chunked": Streamed(_big_chunked),
}


def _state(project: ProxyProject) -> dict:
    return json.loads((project.root / "var" / "run" / "engine-state.json").read_text())


def _extra(project: ProxyProject) -> dict[str, int]:
    time.sleep(3.2)  # HEALTH environ 1 fois/s, etat du moteur ecrit toutes les 2 s
    return {key: int(value) for key, value in _state(project)["extra"].items() if value.isdigit()}


def _rss_kib(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def _dechunk(body: bytes) -> tuple[bytes, bool]:
    """(corps decode, bloc final vu)."""
    decoded, position = bytearray(), 0
    while True:
        end = body.find(b"\r\n", position)
        if end < 0:
            return bytes(decoded), False
        size = int(body[position:end].split(b";")[0], 16)
        if size == 0:
            return bytes(decoded), True
        decoded += body[end + 2:end + 2 + size]
        if len(body) < end + 2 + size + 2:
            return bytes(decoded), False
        position = end + 2 + size + 2


def _read_one(sock: socket.socket, buffer: bytearray) -> tuple[bytes, dict[str, str], bytes]:
    """Une reponse lue sur une connexion gardee (Content-Length ou chunked) : (ligne de statut, en-tetes, corps)."""
    while b"\r\n\r\n" not in buffer:
        buffer += sock.recv(65536)
    head, _, rest = bytes(buffer).partition(b"\r\n\r\n")
    buffer[:] = rest
    lines = head.split(b"\r\n")
    headers = {name.strip().lower().decode(): value.strip().decode()
               for name, _, value in (line.partition(b":") for line in lines[1:])}
    if headers.get("transfer-encoding") == "chunked":
        while b"0\r\n\r\n" not in buffer:
            buffer += sock.recv(65536)
        end = bytes(buffer).index(b"0\r\n\r\n") + 5
        body, finished = _dechunk(bytes(buffer[:end]))
        assert finished
        del buffer[:end]
        return lines[0], headers, body
    length = int(headers.get("content-length", "0"))
    while len(buffer) < length:
        buffer += sock.recv(65536)
    body = bytes(buffer[:length])
    del buffer[:length]
    return lines[0], headers, body


def _raw_request(target: str, address: str, version: str = "HTTP/1.1", close: bool = True) -> bytes:
    return (f"GET {target} {version}\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\n"
            + ("Connection: close\r\n" if close else "") + "\r\n").encode()


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeStreamingRelay(unittest.TestCase):
    """Un projet relaye par le natif pour toute la classe (read_timeout 1 s)."""

    @classmethod
    def setUpClass(cls):
        cls.backend = ScriptedBackend(SCRIPTS)
        cls.project = ProxyProject("native", cls.backend.port, proxy=NATIVE_RELAY)
        cls.project.start()
        assert cls.project.effective_engine() == "native"

    @classmethod
    def tearDownClass(cls):
        cls.project.stop()
        cls.backend.stop()

    def _connect(self) -> socket.socket:
        sock = socket.create_connection(("127.0.0.1", self.project.port), timeout=10)
        self.addCleanup(sock.close)
        return sock

    def test_chunked_relayed_in_chunked_without_trailers(self):
        offsets = self.project.log_offsets()
        status, headers, body, raw = self.project.request("GET", "/api/trailers")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("transfer-encoding"), ["chunked"])
        self.assertNotIn("content-length", headers)
        decoded, finished = _dechunk(body)
        self.assertEqual((decoded, finished), (b"hello world", True))
        self.assertNotIn(b"X-Trailer", raw)  # trailers valides puis retires (§2.1 point 3)
        self.assertNotIn(b"ext=1", raw)      # decoupage du serveur, jamais celui du backend
        lines = self.project.new_lines("access", offsets)
        self.assertTrue(any('"GET /api/trailers HTTP/1.1" 200 11 ' in line for line in lines), lines)  # P2

    def test_response_streams_before_the_backend_finishes(self):
        sock = self._connect()
        started = time.monotonic()
        sock.sendall(_raw_request("/api/stream-slow", self.project.next_address()))
        received = b""
        while b"debut" not in received:
            received += sock.recv(65536)
        first = time.monotonic() - started
        while b"0\r\n\r\n" not in received:
            data = sock.recv(65536)
            if not data:
                break
            received += data
        total = time.monotonic() - started
        self.assertLess(first, 0.5, "premier bloc retenu jusqu'a la fin de la reponse")
        self.assertGreaterEqual(total, 0.75)
        self.assertEqual(_dechunk(received.split(b"\r\n\r\n", 1)[1]), (b"debutfin", True))

    def test_close_delimited_response_keeps_the_client_connection(self):
        sock = self._connect()
        address = self.project.next_address()
        sock.sendall(_raw_request("/api/close", address, close=False) + _raw_request("/", address, close=False))
        buffer = bytearray()
        first = _read_one(sock, buffer)
        second = _read_one(sock, buffer)
        self.assertEqual((first[0], first[1].get("transfer-encoding"), first[2]),
                         (b"HTTP/1.1 200 OK", "chunked", b"fin-par-fermeture"))
        self.assertEqual((second[0], second[2]), (b"HTTP/1.1 200 OK", b"site local"))

    def test_http10_client_gets_a_body_ended_by_close(self):
        raw = self.project.exchange(_raw_request("/api/chunked", self.project.next_address(), "HTTP/1.0", close=False))
        head, _, body = raw.partition(b"\r\n\r\n")
        self.assertIn(b"Connection: close", head)
        self.assertNotIn(b"Transfer-Encoding", head)
        self.assertNotIn(b"Content-Length", head)
        self.assertEqual(body, b"hello world")

    def test_empty_error_body_gets_the_error_page_like_python(self):
        for target, status in (("/api/empty-404", 404), ("/api/empty-503-close", 503)):
            got, headers, body, _raw = self.project.request("GET", target)
            self.assertEqual(got, status)
            self.assertIn("content-length", headers)  # decide avant l'envoi de la tete : page complete (C7)
            self.assertIn(b"<html", body.lower())

    def test_large_responses_arrive_intact(self):
        sock = self._connect()
        address = self.project.next_address()
        sock.sendall(_raw_request("/api/big", address, close=False) + _raw_request("/api/big-chunked", address))
        buffer = bytearray()
        _line, headers, body = _read_one(sock, buffer)
        self.assertEqual(headers.get("content-length"), str(BIG))
        self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(BIG_BODY).hexdigest())
        _line, headers, body = _read_one(sock, buffer)
        self.assertEqual(headers.get("transfer-encoding"), "chunked")
        self.assertEqual(body, BIG_BODY[:65536] * BIG_CHUNKED_PARTS)

    def test_slow_client_keeps_native_memory_bounded(self):
        pid = int(_state(self.project)["native_pid"])
        before = _rss_kib(pid)
        sock = self._connect()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.sendall(_raw_request("/api/big", self.project.next_address()))
        time.sleep(2)  # client qui ne lit pas : le backend (32 Mio) va bien plus vite
        during = _rss_kib(pid)
        received = 0
        while True:
            data = sock.recv(1 << 20)
            if not data:
                break
            received += len(data)
        self.assertGreater(received, BIG)
        # C12 : tampon borne par connexion (marque haute 128 Kio) - jamais la reponse entiere en memoire.
        self.assertLess(during - before, 8 * 1024, f"RSS {before} -> {during} Kio")

    def test_backend_cut_after_the_head_closes_the_client_and_logs_partial_size(self):
        offsets = self.project.log_offsets()
        raw = self.project.exchange(_raw_request("/api/cut", self.project.next_address()))
        head, _, body = raw.partition(b"\r\n\r\n")
        self.assertTrue(head.startswith(b"HTTP/1.1 200 "))  # C4 : la reponse commencee n'est jamais remplacee
        self.assertIn(b"Content-Length: 1000000", head)
        self.assertEqual(len(body), 100_000)
        access = self.project.new_lines("access", offsets)
        self.assertTrue(any('"GET /api/cut HTTP/1.1" 200 100000 ' in line for line in access), access)  # P2
        errors = self.project.new_lines("error", offsets, wait=0)
        self.assertTrue([line for line in errors if "interrompue" in line], errors)

    def test_read_timeout_between_blocks_cuts_the_stream(self):
        offsets = self.project.log_offsets()
        started = time.monotonic()
        raw = self.project.exchange(_raw_request("/api/stall", self.project.next_address()), timeout=10)
        self.assertLess(time.monotonic() - started, 2.8)  # read_timeout_seconds = 1, au pas de 250 ms
        body, finished = _dechunk(raw.partition(b"\r\n\r\n")[2])
        self.assertEqual((body, finished), (b"debut", False))  # jamais de bloc final : le client voit la coupure
        errors = self.project.new_lines("error", offsets)
        self.assertTrue([line for line in errors if "délai de lecture dépassé" in line], errors)
        access = self.project.new_lines("access", offsets, wait=0)
        self.assertTrue(any('"GET /api/stall HTTP/1.1" 200 5 ' in line for line in access), access)

    def test_client_leaving_mid_stream_logs_status_sent_never_499(self):
        offsets = self.project.log_offsets()
        sock = socket.create_connection(("127.0.0.1", self.project.port), timeout=10)
        sock.sendall(_raw_request("/api/big", self.project.next_address()))
        received = 0
        while received < (1 << 20):
            received += len(sock.recv(65536))
        sock.close()
        time.sleep(1)
        lines = [line for line in self.project.new_lines("access", offsets) if "/api/big " in line]
        self.assertEqual(len(lines), 1, lines)
        size = int(lines[0].split('" 200 ', 1)[1].split()[0])  # P3 : statut reellement envoye, octets partiels
        self.assertGreater(size, 0)
        self.assertLess(size, BIG)

    def test_pool_reuses_connections_for_get_never_for_post(self):
        before = self.backend.connections
        for _ in range(10):
            self.assertEqual(self.project.request("GET", "/api/ok")[0], 200)
        self.assertLessEqual(self.backend.connections - before, 2, "pool : une connexion par fil au plus ici")
        before = self.backend.connections
        for _ in range(4):
            self.assertEqual(self.project.request("POST", "/api/echo", body=b"x=1")[0], 200)
        self.assertEqual(self.backend.connections - before, 4)  # D42 : jamais une connexion du pool

    def test_zz_reservations_return_to_zero(self):
        # Dernier de la classe (ordre alphabetique) : tous les chemins ci-dessus parcourus.
        extra = _extra(self.project)
        self.assertEqual((extra["proxy_pending_body"], extra["proxy_inspections"]), (0, 0))
        self.assertEqual(extra["upstream_connections"], extra["upstream_idle"])
        self.assertLessEqual(extra["upstream_idle"], 256)  # lot 11 : moitie du budget par defaut (512)


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeRelayLimits(unittest.TestCase):
    """Un projet par test : reglages propres (limite de corps, delai d'ecriture, backend qui coupe)."""

    def _project(self, backend: ScriptedBackend, engine: str = "native", **settings) -> ProxyProject:
        self.addCleanup(backend.stop)
        project = ProxyProject(engine, backend.port, proxy=NATIVE_RELAY if engine == "native" else None, **settings)
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), engine)
        return project

    def test_close_delimited_over_the_limit_is_cut(self):
        backend = ScriptedBackend(SCRIPTS)
        self.addCleanup(backend.stop)
        project = ProxyProject("native", backend.port, proxy={**NATIVE_RELAY, "max_response_body_mb": 1})
        self.addCleanup(project.stop)
        project.start()
        offsets = project.log_offsets()
        raw = project.exchange(_raw_request("/api/close-big", project.next_address()), timeout=10)
        body, finished = _dechunk(raw.partition(b"\r\n\r\n")[2])
        self.assertEqual((len(body), finished), (1 << 20, False))
        errors = project.new_lines("error", offsets)
        self.assertTrue([line for line in errors if "coupée" in line and "max_response_body_mb" in line], errors)
        access = project.new_lines("access", offsets, wait=0)
        self.assertTrue(any(f'"GET /api/close-big HTTP/1.1" 200 {1 << 20} ' in line for line in access), access)

    def test_client_that_stops_reading_is_cut_after_the_write_timeout(self):
        project = self._project(ScriptedBackend(SCRIPTS), server={"write_timeout_seconds": 2})
        offsets = project.log_offsets()
        sock = socket.create_connection(("127.0.0.1", project.port), timeout=10)
        self.addCleanup(sock.close)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.sendall(_raw_request("/api/big", project.next_address()))
        time.sleep(4)
        lines = [line for line in project.new_lines("access", offsets) if "/api/big " in line]
        self.assertEqual(len(lines), 1, lines)  # D31 : coupe, ligne ecrite sans que le client lise
        self.assertLess(int(lines[0].split('" 200 ', 1)[1].split()[0]), BIG)

    def test_dead_pooled_connection_is_retried_once_in_both_engines(self):
        for engine in ("python", "native"):
            with self.subTest(engine=engine):
                backend = ScriptedBackend(drop_reused=True)
                project = self._project(backend, engine)
                statuses = [project.request("GET", "/api/ok")[0] for _ in range(3)]
                self.assertEqual(statuses, [200, 200, 200])  # C8 : connexion morte avant la reponse -> reprise
                self.assertGreaterEqual(backend.dropped, 1)
                self.assertEqual(backend.hits_for("/api/ok"), 3)  # requete jamais executee deux fois
                posts = [project.request("POST", "/api/echo", body=b"x=1")[0] for _ in range(2)]
                self.assertEqual(posts, [200, 200])  # D42 : POST sur une connexion neuve, jamais rejoue
                if engine == "native":
                    self.assertGreaterEqual(_extra(project)["upstream_retries"], 1)

    def _concurrent_gets(self, project: ProxyProject, count: int) -> list[int]:
        addresses = [project.next_address() for _ in range(count)]
        with ThreadPoolExecutor(count) as pool:
            return list(pool.map(lambda address: project.request("GET", "/api/stream-slow", address=address)[0],
                                 addresses))

    def test_pool_keeps_more_than_ten_idle_connections(self):
        # Lot 11 (mesures, 2026-11-14) : 32 connexions inactives par backend et par fil ; au lot 5, 10 en tout.
        backend = ScriptedBackend(SCRIPTS)
        project = self._project(backend)
        self.assertEqual(self._concurrent_gets(project, 12), [200] * 12)
        self.assertEqual(backend.connections, 12)
        extra = _extra(project)
        self.assertEqual((extra["upstream_idle"], extra["upstream_connections"]), (12, 12))

    def test_idle_connections_stay_under_half_the_budget(self):
        # Lot 11 : la moitie de max_upstream_connections reste libre pour les connexions neuves (un fil sans
        # connexion inactive a evincer n'est jamais bloque par celles des autres fils). Deux fils peuvent verifier en
        # meme temps : un depassement d'une connexion par fil supplementaire reste possible.
        backend = ScriptedBackend(SCRIPTS)
        self.addCleanup(backend.stop)
        project = ProxyProject("native", backend.port, proxy={**NATIVE_RELAY, "max_upstream_connections": 8})
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(self._concurrent_gets(project, 6), [200] * 6)
        extra = _extra(project)
        self.assertEqual(extra["upstream_connections"], extra["upstream_idle"])
        self.assertGreaterEqual(extra["upstream_idle"], 4)
        self.assertLessEqual(extra["upstream_idle"], 5)


if __name__ == "__main__":
    unittest.main()
