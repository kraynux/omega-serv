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


    async def _raw(self, data: bytes) -> bytes:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(data)
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        writer.close()
        return response

    def _access_lines(self) -> list[str]:
        path = self.root / self.config.logs.access
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    async def test_unknown_major_version_gets_505(self):
        # Plan moteur C++ §14 (2026-11-02) : HTTP/9.9 etait servi en 200.
        for version in (b"HTTP/9.9", b"HTTP/2.0", b"HTTP/0.9"):
            response = await self._raw(b"GET /index.html " + version + b"\r\nHost: test\r\n\r\n")
            self.assertTrue(response.startswith(b"HTTP/1.1 505 "), version)

    async def test_malformed_version_gets_400(self):
        for version in (b"HTTP/abc", b"HTTP/1.1.1", b"HTTP/11", b"HTTP/1.\xd9\xa1"):
            response = await self._raw(b"GET /index.html " + version + b"\r\nHost: test\r\n\r\n")
            self.assertTrue(response.startswith(b"HTTP/1.1 400 "), version)

    async def test_higher_minor_version_is_served_as_1_1(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        request = b"GET /index.html HTTP/1.7\r\nHost: test\r\n\r\n"
        writer.write(request + request)  # keep-alive comme en 1.1 : deux reponses sur la meme connexion
        await writer.drain()
        data = b""
        while data.count(b"hello world") < 2:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=3)
            self.assertTrue(chunk, data)
            data += chunk
        writer.close()
        self.assertEqual(data.count(b"HTTP/1.1 200 OK"), 2)

    async def test_absolute_form_target_is_accepted(self):
        for target in (b"http://exemple.test/index.html", b"HTTPS://exemple.test/index.html?x=1"):
            response = await self._raw(b"GET " + target + b" HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n")
            self.assertTrue(response.startswith(b"HTTP/1.1 200 "), target)
            self.assertIn(b"hello world", response)
        # chemin absent : la racine (index.html)
        response = await self._raw(b"GET http://exemple.test HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n")
        self.assertTrue(response.startswith(b"HTTP/1.1 200 "))
        # la ligne d'acces garde la cible telle que recue
        self.assertIn('"GET http://exemple.test/index.html HTTP/1.1" 200', "\n".join(self._access_lines()))

    async def test_invalid_absolute_form_target_gets_400(self):
        for target in (b"http:///index.html", b"http://user@exemple.test/", b"http://a\x01b/"):
            response = await self._raw(b"GET " + target + b" HTTP/1.1\r\nHost: test\r\n\r\n")
            self.assertTrue(response.startswith(b"HTTP/1.1 400 "), target)

    async def test_http_1_0_without_host_still_rejected(self):
        response = await self._raw(b"GET /index.html HTTP/1.0\r\n\r\n")
        self.assertTrue(response.startswith(b"HTTP/1.1 400 "))

    async def test_parse_errors_are_written_to_access_log(self):
        # Plan moteur C++ §14 (valide 2026-11-02) : visibles par fail2ban et RIPOSTE.
        await self._raw(b"GET /a HTTP/9.9\r\nHost: test\r\nUser-Agent: scan\r\n\r\n")
        await self._raw(b"GET /b HTTP/1.1\r\nHost: test\r\nUser-Agent: ua2\r\nX-A : 1\r\n\r\n")
        await self._raw(b"GET /" + b"x" * 9000 + b" HTTP/1.1\r\nHost: test\r\n\r\n")
        await self._raw(b"GET /c HTTP/1.1\r\nHost: a\r\nHost: b\r\n\r\n")
        await self._raw(b"GET /d HTTP/1.1\r\nHost: test\r\nContent-Length: 1_0\r\n\r\n")
        lines = self._access_lines()
        self.assertEqual(len(lines), 5, lines)
        self.assertRegex(lines[0], r'^127\.0\.0\.1 - - \[[^\]]+\] "GET /a HTTP/9\.9" 505 \d+ "-" "-" [0-9a-f]{16}$')  # refusee avant les en-tetes
        self.assertRegex(lines[1], r'"GET /b HTTP/1\.1" 400 \d+ "-" "ua2" ')  # en-tetes lus avant l'erreur
        self.assertRegex(lines[2], r'\] "-" 414 \d+ "-" "-" ')
        self.assertRegex(lines[3], r'"GET /c HTTP/1\.1" 400 ')
        self.assertRegex(lines[4], r'"GET /d HTTP/1\.1" 400 ')

if __name__ == "__main__":
    unittest.main()
