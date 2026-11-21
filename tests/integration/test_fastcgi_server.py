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
        status, _, _ = await self._request("GET", "/app/index.php")
        self.assertEqual(status, 503)

    async def test_traversal_outside_script_root_rejected(self):
        status, _, _ = await self._request("GET", "/app/../../../../etc/passwd")
        self.assertNotEqual(status, 200)


class TestFastCgiZonesIntegration(unittest.IsolatedAsyncioTestCase):
    """Projets 3.0.0 §8.1 : plusieurs zones, chacune avec sa racine et sa socket (un pool PHP-FPM par zone), le plus
    long prefixe l'emporte, et une zone desactivee repond 503 meme si son PHP-FPM tourne."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot" / "blog").mkdir(parents=True)
        (self.root / "webroot" / "blog" / "index.php").write_text("never served as a file")
        for name in ("blog-app", "admin-app", "wiki-app"):
            (self.root / name).mkdir()
            (self.root / name / "index.php").write_text("<?php ?>")
        (self.root / "run").mkdir()
        zone = {"connect_timeout_seconds": 3, "read_timeout_seconds": 3}
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"fastcgi": {"enabled": True, "zones": [
                {**zone, "url_prefix": "/blog/", "script_root": "blog-app", "socket_path": "run/blog.sock"},
                {**zone, "url_prefix": "/blog/admin/", "script_root": "admin-app", "socket_path": "run/admin.sock"},
                {**zone, "url_prefix": "/wiki/", "script_root": "wiki-app", "socket_path": "run/wiki.sock",
                 "enabled": False},
            ]}},
        })
        self.server = build_server(self.config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]
        for name in ("blog", "admin", "wiki"):
            task = asyncio.create_task(_fake_php_fpm(self.root / "run" / f"{name}.sock",
                                                     b"Content-Type: text/plain\r\n\r\n" + name.encode()))
            self.addAsyncCleanup(self._stop, task)
        await asyncio.sleep(0.05)

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def _stop(self, task):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001, S110
            pass

    def _get_sync(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    async def _get(self, path):
        return await asyncio.to_thread(self._get_sync, path)

    async def test_each_zone_reaches_its_own_pool(self):
        self.assertEqual(await self._get("/blog/index.php"), (200, b"blog"))
        self.assertEqual(await self._get("/blog/admin/index.php"), (200, b"admin"))

    async def test_disabled_zone_answers_503_while_others_keep_running(self):
        status, _ = await self._get("/wiki/index.php")
        self.assertEqual(status, 503)
        self.assertEqual(await self._get("/blog/"), (200, b"blog"))


class TestFastCgiZoneRequestSize(unittest.IsolatedAsyncioTestCase):
    """Projets 3.0.0 §9 (decision de l'auteur du 2026-11-16) : une zone FastCGI fixe sa propre taille maximale de
    requete, plus grande ou plus petite que la taille globale ; sans valeur, la taille globale s'applique."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        for name in ("admin-app", "public-app", "plain-app"):
            (self.root / name).mkdir()
            (self.root / name / "index.php").write_text("<?php ?>")
        (self.root / "run").mkdir()
        zone = {"connect_timeout_seconds": 3, "read_timeout_seconds": 3}
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0, "max_request_size": 1000},
            "security": {"allowed_methods": ["GET", "HEAD", "POST"]},
            "options": {"fastcgi": {"enabled": True, "zones": [
                {**zone, "url_prefix": "/admin/", "script_root": "admin-app", "socket_path": "run/admin.sock",
                 "max_request_size": 5000},
                {**zone, "url_prefix": "/public/", "script_root": "public-app", "socket_path": "run/public.sock",
                 "max_request_size": 100},
                {**zone, "url_prefix": "/plain/", "script_root": "plain-app", "socket_path": "run/plain.sock"},
            ]}},
        })
        self.server = build_server(self.config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]
        for name in ("admin", "public", "plain"):
            task = asyncio.create_task(_fake_php_fpm(self.root / "run" / f"{name}.sock",
                                                     b"Content-Type: text/plain\r\n\r\n" + name.encode()))
            self.addAsyncCleanup(self._stop, task)
        await asyncio.sleep(0.05)

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def _stop(self, task):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001, S110
            pass

    def _post_sync(self, path, size):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("POST", path, body=b"x" * size, headers={"Content-Type": "application/octet-stream"})
            resp = conn.getresponse()
            resp.read()
            return resp.status
        finally:
            conn.close()

    async def _post(self, path, size):
        return await asyncio.to_thread(self._post_sync, path, size)

    async def test_larger_zone_accepts_what_the_global_size_refuses(self):
        self.assertEqual(await self._post("/admin/index.php", 3000), 200)
        self.assertEqual(await self._post("/admin/index.php", 6000), 413)

    async def test_smaller_zone_refuses_under_the_global_size(self):
        self.assertEqual(await self._post("/public/index.php", 50), 200)
        self.assertEqual(await self._post("/public/index.php", 500), 413)

    async def test_zone_without_its_own_size_keeps_the_global_one(self):
        self.assertEqual(await self._post("/plain/index.php", 900), 200)
        self.assertEqual(await self._post("/plain/index.php", 3000), 413)


if __name__ == "__main__":
    unittest.main()
