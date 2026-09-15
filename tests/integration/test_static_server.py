# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase 1 (spec §30.2) : serveur reel, connexions
TCP reelles sur 127.0.0.1, aucun mock. http.client (bloquant) est
execute via asyncio.to_thread pour ne jamais geler la boucle evenements
qui fait tourner le serveur pendant le test - un appel bloquant direct
sur la meme boucle causerait un blocage mutuel (le serveur ne pourrait
jamais traiter la connexion pendant que le test attend une reponse)."""
import asyncio
import http.client
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class TestStaticServerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello world")
        (webroot / ".env").write_text("SECRET=1")
        (self.root / "secure").mkdir()
        (self.root / "secure" / "secret.txt").write_text("nope")

        self.config = OmegaServConfig.from_dict({
            "server": {
                "bind": "127.0.0.1",
                "port": 0,
                "max_header_size": 300,
                "max_request_size": 100,
                "read_timeout_seconds": 1,
                "keepalive_timeout_seconds": 1,
                "max_keepalive_requests": 2,
            },
            "security": {
                "allowed_methods": ["GET", "HEAD", "POST"],
            },
        })
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

    async def test_get_static_file(self):
        status, headers, data = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"hello world")
        self.assertIn("text/html", headers["Content-Type"])

    async def test_head_static_file_has_no_body(self):
        status, headers, data = await self._request("HEAD", "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"")
        self.assertEqual(headers["Content-Length"], "11")

    async def test_missing_file_is_404(self):
        status, _, _ = await self._request("GET", "/nope.html")
        self.assertEqual(status, 404)

    async def test_dotfile_is_403(self):
        status, _, _ = await self._request("GET", "/.env")
        self.assertEqual(status, 403)

    async def test_traversal_is_403(self):
        status, _, _ = await self._request("GET", "/../secure/secret.txt")
        self.assertEqual(status, 403)

    async def test_percent_encoded_traversal_is_403(self):
        status, _, _ = await self._request("GET", "/%2e%2e/secure/secret.txt")
        self.assertEqual(status, 403)

    async def test_missing_file_gets_default_html_error_page(self):
        status, headers, data = await self._request("GET", "/nope.html")
        self.assertEqual(status, 404)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"404", data)
        self.assertIn(b"Not Found", data)

    async def test_custom_error_page_overrides_default_when_option_enabled(self):
        errors_dir = self.root / "webroot" / ".errors"
        errors_dir.mkdir()
        (errors_dir / "404.html").write_text("<html>404 sur mesure</html>")

        new_options = dict(self.config.options)
        new_options["error_pages"] = Option(name="error_pages", enabled=True, settings={"custom_dir": "webroot/.errors"})
        self.config = replace(self.config, options=new_options)
        await self.server.close()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        status, _, data = await self._request("GET", "/nope.html")
        self.assertEqual(status, 404)
        self.assertEqual(data, b"<html>404 sur mesure</html>")

    async def test_access_control_denies_prefix_but_allows_more_specific_child(self):
        private_dir = self.root / "webroot" / "private"
        private_dir.mkdir()
        (private_dir / "secret.txt").write_text("nope")
        assets_dir = private_dir / ".assets"
        assets_dir.mkdir()
        (assets_dir / "logo.png").write_text("fake-png")

        new_options = dict(self.config.options)
        new_options["access_control"] = Option(name="access_control", enabled=True, settings={
            "list": [
                {"path_prefix": "/private/", "verdict": "deny"},
                {"path_prefix": "/private/.assets/", "verdict": "allow"},
            ],
        })
        self.config = replace(self.config, options=new_options)
        await self.server.close()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        status, _, _ = await self._request("GET", "/private/secret.txt")
        self.assertEqual(status, 403)
        status, _, data = await self._request("GET", "/private/.assets/logo.png")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"fake-png")
        status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)

    async def test_healthz_endpoint(self):
        status, _, data = await self._request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"OK")

    async def test_header_size_limit_returns_431(self):
        status, _, _ = await self._request("GET", "/index.html", headers={"X-Big": "a" * 1000})
        self.assertEqual(status, 431)

    async def test_body_size_limit_returns_413(self):
        status, _, _ = await self._request("POST", "/", body=b"x" * 500)
        self.assertEqual(status, 413)

    async def test_keepalive_limit_enforced(self):
        def _run():
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
            try:
                conn.request("GET", "/index.html")
                r1 = conn.getresponse()
                r1.read()
                conn.request("GET", "/index.html")
                r2 = conn.getresponse()
                r2.read()
                return r2.status, r2.getheader("Connection")
            finally:
                conn.close()

        status, connection_header = await asyncio.to_thread(_run)
        self.assertEqual(status, 200)
        self.assertEqual(connection_header, "close")

    async def test_slow_client_times_out(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /index.html ")  # ligne de requete deliberement incomplete
        await writer.drain()
        await asyncio.sleep(1.5)  # depasse read_timeout_seconds=1
        data = await reader.read(100)
        self.assertEqual(data, b"")  # connexion fermee par le serveur, pas de reponse
        writer.close()

    async def test_slow_body_times_out(self):
        # Retour utilisateur (audit securite) : variante "slow-POST" (type
        # R-U-Dead-Yet) - en-tetes complets et valides envoyes tout de
        # suite (Content-Length: 10), mais AUCUN octet de corps n'est
        # jamais envoye. Avant correctif, la lecture du corps n'etait
        # bornee par aucun timeout et la connexion restait ouverte
        # indefiniment - doit desormais expirer comme la lecture des
        # en-tetes, avec une reponse 408 explicite (le corps a ete promis
        # via Content-Length, contrairement au cas ci-dessus ou meme la
        # ligne de requete est incomplete).
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"POST / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 10\r\n\r\n")
        await writer.drain()
        await asyncio.sleep(1.5)  # depasse read_timeout_seconds=1, aucun octet de corps envoye
        data = await reader.read(200)
        self.assertIn(b"408", data)
        writer.close()


if __name__ == "__main__":
    unittest.main()
