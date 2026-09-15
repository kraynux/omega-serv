# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase 8 (FastCGI/PHP-FPM) : serveur HTTP reel,
connexions TCP reelles, et un faux backend FastCGI (vrai socket Unix,
vrai protocole sur le fil) qui tient lieu de PHP-FPM - aucun mock, meme
discipline que les autres suites d'integration. PHP-FPM n'etant pas
installe sur cette machine, ce faux backend est la seule maniere de
verifier le pipeline complet de bout en bout."""
import asyncio
import http.client
import struct
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.fastcgi_protocol import (
    FCGI_BEGIN_REQUEST,
    FCGI_END_REQUEST,
    FCGI_PARAMS,
    FCGI_REQUEST_COMPLETE,
    FCGI_STDIN,
    FCGI_STDOUT,
    decode_record_header,
    encode_record,
)
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


async def _fake_php_fpm(socket_path: Path, response_body: bytes):
    async def handle(reader, writer):
        request_id = 1
        params_done = stdin_done = False
        received_stdin = bytearray()
        while not (params_done and stdin_done):
            header = decode_record_header(await reader.readexactly(8))
            content = await reader.readexactly(header.content_length) if header.content_length else b""
            if header.padding_length:
                await reader.readexactly(header.padding_length)
            if header.type == FCGI_BEGIN_REQUEST:
                request_id = header.request_id
            elif header.type == FCGI_PARAMS and not content:
                params_done = True
            elif header.type == FCGI_STDIN:
                if not content:
                    stdin_done = True
                else:
                    received_stdin.extend(content)

        body = response_body
        if b"{{ECHO_STDIN}}" in body:
            body = body.replace(b"{{ECHO_STDIN}}", bytes(received_stdin))

        writer.write(encode_record(FCGI_STDOUT, request_id, body))
        writer.write(encode_record(FCGI_STDOUT, request_id, b""))
        writer.write(encode_record(FCGI_END_REQUEST, request_id, struct.pack("!IB3x", 0, FCGI_REQUEST_COMPLETE)))
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=str(socket_path))
    async with server:
        await server.serve_forever()


class TestFastCgiServerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("static ok")

        self.script_root = self.root / "php-app"
        self.script_root.mkdir()
        (self.script_root / "index.php").write_text("<?php echo 'hello'; ?>")

        self.socket_path = self.root / "var" / "run" / "php-fpm.sock"
        self.socket_path.parent.mkdir(parents=True)

        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "security": {"allowed_methods": ["GET", "HEAD", "POST"]},
            "options": {"fastcgi": {
                "enabled": True,
                "url_prefix": "/app/",
                "script_root": "php-app",
                "socket_path": "var/run/php-fpm.sock",
                "connect_timeout_seconds": 3,
                "read_timeout_seconds": 3,
            }},
        })
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def _start_fake_php_fpm(self, response_body: bytes):
        task = asyncio.create_task(_fake_php_fpm(self.socket_path, response_body))
        await asyncio.sleep(0.05)
        self.addAsyncCleanup(self._stop_fake_php_fpm, task)

    async def _stop_fake_php_fpm(self, task):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001, S110
            # Nettoyage de test best-effort : on vient d'annuler la tache,
            # peu importe ce qu'elle a leve en reponse (CancelledError
            # attendu, ou toute autre exception issue de la fermeture
            # brutale du socket cote faux PHP-FPM) - ne doit jamais faire
            # echouer le teardown du test.
            pass

    def _request_sync(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, dict(resp.getheaders()), data
        finally:
            conn.close()

    async def _request(self, method, path, body=None, headers=None):
        return await asyncio.to_thread(self._request_sync, method, path, body, headers)

    async def test_php_response_served_through_full_stack(self):
        await self._start_fake_php_fpm(b"Content-Type: text/html\r\n\r\n<h1>hello from php</h1>")
        status, headers, data = await self._request("GET", "/app/index.php")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"<h1>hello from php</h1>")
        self.assertEqual(headers.get("Content-Type"), "text/html")

    async def test_static_files_still_served_outside_fastcgi_prefix(self):
        status, _, data = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"static ok")

    async def test_status_header_from_php_forwarded(self):
        await self._start_fake_php_fpm(b"Status: 201 Created\r\n\r\ncreated")
        status, _, _ = await self._request("GET", "/app/index.php")
        self.assertEqual(status, 201)

    async def test_security_headers_still_applied_to_fastcgi_response(self):
        await self._start_fake_php_fpm(b"Content-Type: text/html\r\n\r\nbody")
        _, headers, _ = await self._request("GET", "/app/index.php")
        self.assertIn("X-Content-Type-Options", headers)
        self.assertIn("Content-Security-Policy", headers)

    async def test_post_body_forwarded_to_php_via_stdin(self):
        await self._start_fake_php_fpm(b"Content-Type: text/plain\r\n\r\nreceived: {{ECHO_STDIN}}")
        status, _, data = await self._request("POST", "/app/index.php", body=b"field=value")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"received: field=value")

    async def test_missing_php_fpm_socket_returns_503(self):
        # Aucun faux backend demarre - le socket configure n'existe pas.
        status, _, _ = await self._request("GET", "/app/index.php")
        self.assertEqual(status, 503)

    async def test_traversal_outside_script_root_rejected(self):
        status, _, _ = await self._request("GET", "/app/../../../../etc/passwd")
        self.assertNotEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
