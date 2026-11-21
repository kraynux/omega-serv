"""Test d'integration : serveur reel, connexions TCP reelles (meme
discipline que test_static_server.py) - retour utilisateur 2026-09-11
(audit reload/restart) : `server.max_connections` etait configurable et
valide mais applique NULLE PART dans le serveur, vrai bug distinct du
sujet reload/restart lui-meme, corrige dans
infrastructure/server/asyncio_server.py::_handle_connection_tracked."""
import asyncio
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class TestMaxConnections(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello world")
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0, "max_connections": 1},
        })
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def test_connection_over_limit_receives_503(self):
        _reader1, writer1 = await asyncio.open_connection("127.0.0.1", self.port)
        writer1.write(b"GET /index.html ")
        await writer1.drain()
        await asyncio.sleep(0.2)

        try:
            reader2, writer2 = await asyncio.open_connection("127.0.0.1", self.port)
            writer2.write(b"GET /index.html HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            await writer2.drain()
            data = await reader2.read(200)
            self.assertIn(b"503", data)
            writer2.close()
        finally:
            writer1.close()

    async def test_connection_allowed_once_slot_frees_up(self):
        reader1, writer1 = await asyncio.open_connection("127.0.0.1", self.port)
        writer1.write(b"GET /index.html HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer1.drain()
        data1 = await reader1.read(200)
        self.assertIn(b"200", data1)
        writer1.close()
        await asyncio.sleep(0.1)  # laisse le serveur liberer le slot avant la seconde connexion

        reader2, writer2 = await asyncio.open_connection("127.0.0.1", self.port)
        writer2.write(b"GET /index.html HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer2.drain()
        data2 = await reader2.read(200)
        self.assertIn(b"200", data2)
        writer2.close()


class _ServerCase(unittest.IsolatedAsyncioTestCase):
    """Serveur Python reel, projet temporaire ; `_config()` fixe les reglages du cas."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("hello world")
        self.server = build_server(OmegaServConfig.from_dict(self._config()), self.root, LocalFilesystem(),
                                   FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    def _config(self) -> dict:
        raise NotImplementedError

    async def _wait_active(self, expected: int, timeout: float) -> int:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and len(self.server._active_connections) != expected:
            await asyncio.sleep(0.05)
        return len(self.server._active_connections)


class TestTlsHandshakeCountedInCapacity(_ServerCase):
    """Plan proxy natif v2, lot A (D30) : asyncio ne comptait une connexion TLS qu'apres la poignee de main (60 s de
    delai) - 300 connexions muettes tenues avec max_connections = 5 (essai du 2026-11-12)."""

    def _config(self) -> dict:
        certs = Path(self._tmp.name) / "certs"
        certs.mkdir()
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-keyout", str(certs / "key.pem"), "-out", str(certs / "cert.pem"), "-days", "2",
                        "-subj", "/CN=localhost"], check=True, capture_output=True)
        return {"server": {"bind": "127.0.0.1", "port": 0, "max_connections": 2, "read_timeout_seconds": 1},
                "tls": {"enabled": True, "mode": "direct",
                        "certificate": {"certificate_path": "certs/cert.pem", "private_key_path": "certs/key.pem"}}}

    async def test_silent_tls_connections_beyond_capacity_are_closed(self):
        streams = [await asyncio.open_connection("127.0.0.1", self.port) for _ in range(6)]
        try:
            self.assertEqual(await self._wait_active(2, 2.0), 2)
            closed = 0
            for reader, _writer in streams:
                try:
                    if await asyncio.wait_for(reader.read(1), 0.3) == b"":
                        closed += 1
                except (TimeoutError, ConnectionResetError):
                    pass
            self.assertEqual(closed, 4)
        finally:
            for _reader, writer in streams:
                writer.close()

    async def test_handshake_bounded_by_read_timeout(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        try:
            self.assertEqual(await asyncio.wait_for(reader.read(1), 4), b"")  # 1 s, et non plus 60 s
        finally:
            writer.close()


class TestWriteTimeout(_ServerCase):
    """Plan proxy natif v2, lot A (D31) : `server.write_timeout_seconds` etait lu et affiche mais applique nulle part -
    un client qui ne lit pas gardait sa place indefiniment. Delai SANS PROGRES : un client lent qui lit est servi."""

    def _config(self) -> dict:
        with open(Path(self._tmp.name) / "webroot" / "big.bin", "wb") as handle:
            handle.write(b"x" * (24 * 1024 * 1024))
        return {"server": {"bind": "127.0.0.1", "port": 0, "write_timeout_seconds": 1}}

    def _slow_socket(self, receive_buffer: int = 4096) -> socket.socket:
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, receive_buffer)
        sock.connect(("127.0.0.1", self.port))
        sock.sendall(b"GET /big.bin HTTP/1.1\r\nHost: localhost\r\n\r\n")
        return sock

    async def test_client_that_never_reads_is_cut(self):
        sock = self._slow_socket()
        try:
            self.assertEqual(await self._wait_active(1, 2.0), 1)
            self.assertEqual(await self._wait_active(0, 6.0), 0)
        finally:
            sock.close()

    async def test_slow_client_that_keeps_reading_is_served(self):
        # Garde : pauses de 0,1 s (< delai de 1 s) sur un envoi qui dure plusieurs fois le delai - jamais coupe.
        sock = self._slow_socket(receive_buffer=256 * 1024)
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        received, started = 0, time.monotonic()
        try:
            while received < 24 * 1024 * 1024:
                chunk = await asyncio.wait_for(loop.sock_recv(sock, 512 * 1024), 5)
                if not chunk:
                    break  # coupe par le serveur
                received += len(chunk)
                await asyncio.sleep(0.1)
        finally:
            sock.close()
        self.assertGreater(received, 24 * 1024 * 1024)  # en-tetes + corps entier
        self.assertGreater(time.monotonic() - started, 3)  # l'envoi a bien dure plusieurs fois le delai

if __name__ == "__main__":
    unittest.main()
