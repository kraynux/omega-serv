# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.serve_fastcgi import serve_fastcgi
from omega_serv.domain.http.fastcgi_protocol import FastCgiConnectionError
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.routing.fastcgi_zone import FastCgiConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.ports.fastcgi_client_port import FastCgiResult


def _request(path="/app/index.php", method="GET") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method=method,
        path=path, raw_path=path, query="", headers=HttpHeaders.from_pairs([]),
        body=None, content_length=None, is_tls=False,
    )


class _FakeFastCgiClient:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    async def send_request(self, socket_path, env, body, connect_timeout, read_timeout):
        self.calls.append((socket_path, env, body))
        if self._error is not None:
            raise self._error
        return self._result


class TestServeFastCgi(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.script_root = self.root / "php-app"
        self.script_root.mkdir()
        (self.script_root / "index.php").write_text("<?php echo 'hi'; ?>")
        self.filesystem = LocalFilesystem()
        self.resolver = SafePathResolver(self.filesystem, self.script_root)
        self.config = FastCgiConfig(url_prefix="/app/", script_root="php-app")

    def tearDown(self):
        self._tmp.cleanup()

    async def test_successful_response_translated(self):
        client = _FakeFastCgiClient(result=FastCgiResult(
            status_code=200, headers=(("Content-Type", "text/html"),), body=b"<h1>hi</h1>", stderr=b"",
        ))
        response = await serve_fastcgi(_request("/app/index.php"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"<h1>hi</h1>")
        self.assertEqual(response.headers["Content-Type"], "text/html")

    async def test_script_filename_is_absolute_path(self):
        client = _FakeFastCgiClient(result=FastCgiResult(200, (), b"", b""))
        await serve_fastcgi(_request("/app/index.php"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        env = client.calls[0][1]
        self.assertEqual(env["SCRIPT_FILENAME"], str(self.script_root / "index.php"))

    async def test_directory_request_resolves_index_file(self):
        client = _FakeFastCgiClient(result=FastCgiResult(200, (), b"", b""))
        response = await serve_fastcgi(_request("/app/"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 200)
        env = client.calls[0][1]
        self.assertEqual(env["SCRIPT_FILENAME"], str(self.script_root / "index.php"))

    async def test_missing_script_is_404(self):
        client = _FakeFastCgiClient(result=None)
        response = await serve_fastcgi(_request("/app/missing.php"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 404)
        self.assertEqual(client.calls, [])

    async def test_disallowed_extension_is_403(self):
        (self.script_root / "secret.txt").write_text("nope")
        client = _FakeFastCgiClient(result=None)
        response = await serve_fastcgi(_request("/app/secret.txt"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 403)
        self.assertEqual(client.calls, [])

    async def test_traversal_attempt_rejected(self):
        client = _FakeFastCgiClient(result=None)
        response = await serve_fastcgi(_request("/app/../../../etc/passwd"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertNotEqual(response.status, 200)
        self.assertEqual(client.calls, [])

    async def test_fastcgi_connection_error_is_503(self):
        client = _FakeFastCgiClient(error=FastCgiConnectionError("socket introuvable"))
        response = await serve_fastcgi(_request("/app/index.php"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 503)

    async def test_directory_without_index_is_404(self):
        (self.script_root / "empty-dir").mkdir()
        client = _FakeFastCgiClient(result=None)
        response = await serve_fastcgi(_request("/app/empty-dir/"), self.config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 404)

    async def test_allowed_scripts_whitelist_blocks_non_listed_php_file(self):
        (self.script_root / "helper.php").write_text("<?php // inclusion, jamais appele directement")
        config = FastCgiConfig(url_prefix="/app/", script_root="php-app", allowed_scripts=("index.php",))
        client = _FakeFastCgiClient(result=None)
        response = await serve_fastcgi(_request("/app/helper.php"), config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 403)
        self.assertEqual(client.calls, [])

    async def test_allowed_scripts_whitelist_allows_listed_script(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="php-app", allowed_scripts=("index.php",))
        client = _FakeFastCgiClient(result=FastCgiResult(200, (), b"ok", b""))
        response = await serve_fastcgi(_request("/app/index.php"), config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 200)

    async def test_allowed_scripts_whitelist_allows_nested_script(self):
        (self.script_root / "api").mkdir()
        (self.script_root / "api" / "router.php").write_text("<?php echo 'api'; ?>")
        config = FastCgiConfig(url_prefix="/app/", script_root="php-app", allowed_scripts=("api/router.php",))
        client = _FakeFastCgiClient(result=FastCgiResult(200, (), b"ok", b""))
        response = await serve_fastcgi(_request("/app/api/router.php"), config, self.resolver, self.filesystem, client, self.root, "localhost", 8080)
        self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main()
