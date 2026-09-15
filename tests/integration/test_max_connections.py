# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Test d'integration : serveur reel, connexions TCP reelles (meme
discipline que test_static_server.py) - retour utilisateur 2026-09-11
(audit reload/restart) : `server.max_connections` etait configurable et
valide mais applique NULLE PART dans le serveur, vrai bug distinct du
sujet reload/restart lui-meme, corrige dans
infrastructure/server/asyncio_server.py::_handle_connection_tracked."""
import asyncio
import tempfile
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
        # Requete deliberement incomplete (meme technique que
        # test_static_server.py::test_slow_client_times_out) - garde
        # la premiere connexion comptee comme active sans la terminer.
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


if __name__ == "__main__":
    unittest.main()
