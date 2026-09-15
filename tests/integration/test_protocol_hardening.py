# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase 2 (durcissement HTTP) : liste blanche de
methodes, validation du Host, en-tetes de securite/CSP - contre un
serveur reel, connexions TCP reelles."""
import asyncio
import http.client
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig, ServerConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class TestProtocolHardeningIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello world")

        # port=0 (ephemere, assigne par l'OS) - retour utilisateur
        # 2026-09-10 : seul fichier de ce dossier a utiliser le port par
        # defaut (8080) au lieu d'un port ephemere comme partout
        # ailleurs, ce qui entrait en collision avec un vrai serveur
        # OMEGA-SERV lance en tant que service systemd sur la machine de
        # developpement (le bug qu'on venait de corriger fonctionnait
        # enfin, revelant cette fragilite latente du test).
        self.config = OmegaServConfig(server=ServerConfig(port=0))  # profil standard par defaut : GET/HEAD, headers de securite actifs, host requis
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    def _request_sync(self, method, path, headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, dict(resp.getheaders()), data
        finally:
            conn.close()

    async def _request(self, method, path, headers=None, body=None):
        return await asyncio.to_thread(self._request_sync, method, path, headers, body)

    async def test_post_rejected_by_default_method_allowlist(self):
        status, headers, _ = await self._request("POST", "/index.html")
        self.assertEqual(status, 405)
        self.assertIn("GET", headers["Allow"])

    async def test_security_headers_present_on_every_response(self):
        status, headers, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])

    async def test_security_headers_present_even_on_404(self):
        status, headers, _ = await self._request("GET", "/nope.html")
        self.assertEqual(status, 404)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    async def test_missing_host_rejected(self):
        # http.client envoie toujours un Host par defaut ; on force son
        # absence via une requete brute pour tester le vrai chemin de
        # validation cote serveur.
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /index.html HTTP/1.1\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(200), timeout=2)
        self.assertIn(b"400", response)
        writer.close()

    async def test_duplicate_host_rejected(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /index.html HTTP/1.1\r\nHost: a.com\r\nHost: b.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(200), timeout=2)
        self.assertIn(b"400", response)
        writer.close()

    async def test_expect_100_continue_rejected(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(
            b"POST /index.html HTTP/1.1\r\nHost: test\r\nExpect: 100-continue\r\nContent-Length: 5\r\n\r\n"
        )
        await writer.drain()
        response = await asyncio.wait_for(reader.read(200), timeout=2)
        self.assertIn(b"417", response)
        writer.close()

    async def test_duplicate_content_length_rejected(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(
            b"POST /index.html HTTP/1.1\r\nHost: test\r\nContent-Length: 5\r\nContent-Length: 5\r\n\r\nhello"
        )
        await writer.drain()
        response = await asyncio.wait_for(reader.read(200), timeout=2)
        self.assertIn(b"400", response)
        writer.close()


if __name__ == "__main__":
    unittest.main()
