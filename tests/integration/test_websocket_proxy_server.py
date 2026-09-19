"""Test d'integration bout-en-bout du reverse proxy sortant WebSocket
(OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §4/§14) : serveur OMEGA-SERV
reel, connexion TCP reelle depuis un "navigateur" simule (socket brut,
jamais `http.client` - il ne sait pas garder une connexion ouverte
apres une mise a niveau), et un vrai faux backend WebSocket (vrai
socket TCP) - meme discipline "aucun mock du transport" que le reste de
cette suite de tests.

Piege deja documente (Phase 9, `test_serve_websocket_proxy.py`) :
`AsyncioHttpServer.close()` appelle `Server.wait_closed()` qui, depuis
Python 3.12.1, attend sans limite que toutes les connexions actives se
terminent - chaque test ferme donc explicitement SES DEUX cotes de
connexion (navigateur et upstream) avant la fin, jamais apres."""
import asyncio
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class TestWebsocketProxyServerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        self._upstream_servers: list[asyncio.AbstractServer] = []
        self._opened_writers: list[asyncio.StreamWriter] = []

    async def asyncTearDown(self):
        for writer in self._opened_writers:
            writer.close()
        for server in self._upstream_servers:
            server.close()
        await self.server.close()
        self._tmp.cleanup()

    async def _start_websocket_upstream(self) -> tuple[int, dict]:
        """Backend WebSocket minimal : repond 101 puis relaie ("echo")
        tout ce qu'il reçoit ensuite sur le meme tube - suffisant pour
        prouver un aller-retour reel a travers OMEGA-SERV."""
        received_upgrade_request: dict = {}

        async def handle(reader, writer):
            request_bytes = await reader.read(4096)
            received_upgrade_request["bytes"] = request_bytes
            writer.write(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
            await writer.drain()
            try:
                while True:
                    chunk = await reader.read(4096)
                    if not chunk:
                        break
                    writer.write(b"echo:" + chunk)
                    await writer.drain()
            except (ConnectionResetError, BrokenPipeError, OSError):
                pass

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        self._upstream_servers.append(server)
        port = server.sockets[0].getsockname()[1]
        return port, received_upgrade_request

    async def _start_omega_serv(
        self, upstream_port: int, websocket_enabled: bool = True, read_timeout_seconds: float = 2,
    ) -> None:
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/ws/",
                    "upstreams": [{"host": "127.0.0.1", "port": upstream_port}],
                    "connect_timeout_seconds": 2, "read_timeout_seconds": read_timeout_seconds,
                    "websocket_enabled": websocket_enabled,
                }],
            }},
        })
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def _open_browser_connection(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self._opened_writers.append(writer)
        return reader, writer

    async def test_full_upgrade_and_bidirectional_echo_through_the_real_server(self):
        upstream_port, received_upgrade_request = await self._start_websocket_upstream()
        await self._start_omega_serv(upstream_port)

        reader, writer = await self._open_browser_connection()
        writer.write(
            b"GET /ws/chat HTTP/1.1\r\n"
            b"Host: example.test\r\n"
            b"Connection: Upgrade\r\n"
            b"Upgrade: websocket\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            b"Sec-WebSocket-Version: 13\r\n"
            b"\r\n"
        )
        await writer.drain()

        status_line = await reader.readline()
        self.assertIn(b"101", status_line)
        response_headers = b""
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b""):
                break
            response_headers += line
        self.assertIn(b"Upgrade: websocket", response_headers)

        writer.write(b"hello-through-omega-serv")
        await writer.drain()
        echoed = await reader.readexactly(len(b"echo:hello-through-omega-serv"))
        self.assertEqual(echoed, b"echo:hello-through-omega-serv")

        sent = received_upgrade_request["bytes"].decode("latin-1")
        self.assertIn("GET /ws/chat HTTP/1.1\r\n", sent)
        self.assertIn("connection: Upgrade\r\n", sent)
        self.assertIn("upgrade: websocket\r\n", sent)
        self.assertIn("sec-websocket-key: dGhlIHNhbXBsZSBub25jZQ==\r\n", sent)
        self.assertIn("X-Forwarded-For: 127.0.0.1\r\n", sent)

    async def test_upstream_unreachable_relayed_as_bad_gateway(self):
        dead_server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        dead_port = dead_server.sockets[0].getsockname()[1]
        dead_server.close()
        await dead_server.wait_closed()

        await self._start_omega_serv(dead_port)
        reader, writer = await self._open_browser_connection()
        writer.write(
            b"GET /ws/chat HTTP/1.1\r\nHost: example.test\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n"
        )
        await writer.drain()
        status_line = await reader.readline()
        self.assertIn(b"502", status_line)

    async def test_non_websocket_zone_ignores_upgrade_header(self):
        upstream_port, _received = await self._start_websocket_upstream()
        await self._start_omega_serv(upstream_port, websocket_enabled=False, read_timeout_seconds=0.3)

        reader, writer = await self._open_browser_connection()
        writer.write(
            b"GET /ws/chat HTTP/1.1\r\nHost: example.test\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n"
        )
        await writer.drain()
        status_line = await asyncio.wait_for(reader.readline(), timeout=3)
        self.assertIn(b"502", status_line)


if __name__ == "__main__":
    unittest.main()
