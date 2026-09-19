"""Tests d'integration Phase 7 (Auth) : serveur reel, connexions TCP
reelles, vrai en-tete Basic Auth - meme discipline que
test_waf_server.py/test_tls_server.py."""
import asyncio
import base64
import http.client
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


def _basic_header(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


class TestAuthServerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("public")
        (webroot / "private").mkdir()
        (webroot / "private" / "doc.txt").write_text("secret document")

        auth_dir = self.root / "secure" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "users.json").write_text(json.dumps({
            "version": 1,
            "users": [{"username": "admin", "password_hash": hash_password("hunter2")}],
        }))
        (auth_dir / "zones.json").write_text(json.dumps({
            "version": 1,
            "zones": [{"path_prefix": "/private/", "realm": "Zone privee", "allowed_users": ["admin"]}],
        }))

        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"auth": {"enabled": True}},
        })
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger, SystemClock())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    def _request_sync(self, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("GET", path, headers=headers or {})
            resp = conn.getresponse()
            resp.read()
            return resp.status, dict(resp.getheaders())
        finally:
            conn.close()

    async def _request(self, path, headers=None):
        return await asyncio.to_thread(self._request_sync, path, headers)

    async def test_public_path_needs_no_credentials(self):
        status, _ = await self._request("/index.html")
        self.assertEqual(status, 200)

    async def test_protected_path_without_credentials_is_401(self):
        status, headers = await self._request("/private/doc.txt")
        self.assertEqual(status, 401)
        self.assertEqual(headers.get("WWW-Authenticate"), 'Basic realm="Zone privee"')

    async def test_protected_path_with_correct_credentials_is_200(self):
        status, _ = await self._request("/private/doc.txt", _basic_header("admin", "hunter2"))
        self.assertEqual(status, 200)

    async def test_protected_path_with_wrong_password_is_401(self):
        status, _ = await self._request("/private/doc.txt", _basic_header("admin", "wrong"))
        self.assertEqual(status, 401)

    async def test_protected_path_with_unknown_user_is_401(self):
        status, _ = await self._request("/private/doc.txt", _basic_header("nobody", "whatever"))
        self.assertEqual(status, 401)

    async def test_correct_credentials_but_not_allowed_user_is_403(self):
        (self.root / "secure" / "auth" / "users.json").write_text(json.dumps({
            "version": 1,
            "users": [
                {"username": "admin", "password_hash": hash_password("hunter2")},
                {"username": "other", "password_hash": hash_password("otherpass")},
            ],
        }))
        await self.server.close()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger, SystemClock())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        status, _ = await self._request("/private/doc.txt", _basic_header("other", "otherpass"))
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
