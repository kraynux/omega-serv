# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase 9 : arret propre (angle mort §9.2) contre
un serveur reel, vraies connexions TCP - meme discipline que les autres
suites d'integration."""
import asyncio
import http.client
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class TestGracefulShutdown(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("ok")

        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0, "read_timeout_seconds": 30},
        })
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self._tmp.cleanup()

    async def test_shutdown_with_no_active_connections_returns_zero(self):
        forced = await self.server.shutdown(grace_period_seconds=1.0)
        self.assertEqual(forced, 0)

    async def test_shutdown_drains_a_request_that_finishes_within_grace_period(self):
        def _slow_client():
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            conn.request("GET", "/index.html")
            resp = conn.getresponse()
            resp.read()
            conn.close()

        task = asyncio.create_task(asyncio.to_thread(_slow_client))
        await asyncio.sleep(0.05)  # laisser la connexion s'etablir
        forced = await self.server.shutdown(grace_period_seconds=2.0)
        await task
        self.assertEqual(forced, 0)

    async def test_shutdown_force_closes_connection_stuck_past_grace_period(self):
        # Ouvre une connexion TCP brute qui n'envoie jamais de requete
        # complete - reste bloquee en lecture cote serveur bien au-dela
        # du delai de grace, doit etre coupee de force.
        _reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /index.html HTTP/1.1\r\n")  # requete incomplete, jamais de ligne vide finale
        await writer.drain()
        await asyncio.sleep(0.1)  # laisser la tache serveur s'enregistrer comme active avant shutdown()

        forced = await self.server.shutdown(grace_period_seconds=0.3)
        self.assertEqual(forced, 1)

        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

    async def test_shutdown_closes_listening_socket_first(self):
        await self.server.shutdown(grace_period_seconds=0.5)
        with self.assertRaises((ConnectionRefusedError, OSError)):
            _, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", self.port), timeout=2)
            writer.close()


if __name__ == "__main__":
    unittest.main()
