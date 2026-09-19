"""Tests d'integration Phase 4 : alias, redirections, rewrites,
directory listing, cache, proxy de confiance - contre un serveur reel."""
import asyncio
import http.client
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class _ServerTestBase(unittest.IsolatedAsyncioTestCase):
    config_overrides: ClassVar[dict] = {}

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello world")

        base = {
            "server": {"bind": "127.0.0.1", "port": 0},
        }
        merged = {**base, **self.config_overrides}
        self.config = OmegaServConfig.from_dict(merged)
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


class TestRedirects(_ServerTestBase):
    config_overrides: ClassVar[dict] = {
        "options": {"redirects": {
            "enabled": True,
            "list": [{"url_prefix": "/old", "destination": "/index.html", "status_code": 301}],
        }},
    }

    async def test_redirect_returns_301_with_location(self):
        status, headers, _ = await self._request("GET", "/old/page")
        self.assertEqual(status, 301)
        self.assertEqual(headers["Location"], "/index.html")


class TestRewrites(_ServerTestBase):
    config_overrides: ClassVar[dict] = {
        "options": {"rewrites": {
            "enabled": True,
            "list": [{"match_prefix": "/legacy.html", "replacement_prefix": "/index.html"}],
        }},
    }

    async def test_rewrite_serves_target_file(self):
        status, _, data = await self._request("GET", "/legacy.html")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"hello world")


class TestAlias(_ServerTestBase):
    config_overrides: ClassVar[dict] = {
        "options": {"aliases": {
            "enabled": True,
            "list": [{"url_prefix": "/shared/", "target_path": "shared-data/", "allow_outside_webroot": True}],
        }},
    }

    async def asyncSetUp(self):
        await super().asyncSetUp()
        (self.root / "shared-data").mkdir()
        (self.root / "shared-data" / "report.txt").write_text("shared report")

    async def test_alias_serves_file_outside_webroot(self):
        status, _, data = await self._request("GET", "/shared/report.txt")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"shared report")

    async def test_alias_target_confinement_still_enforced(self):
        status, _, _ = await self._request("GET", "/shared/../../etc/passwd")
        self.assertEqual(status, 403)


class TestDirectoryListing(_ServerTestBase):
    config_overrides: ClassVar[dict] = {
        "options": {"dirlisting": {
            "enabled": True,
            "zone_prefixes": ["/public/"],
        }},
    }

    async def asyncSetUp(self):
        await super().asyncSetUp()
        public_dir = self.root / "webroot" / "public"
        public_dir.mkdir()
        (public_dir / "report.txt").write_text("x")
        (public_dir / ".hidden").write_text("y")
        (self.root / "webroot" / "other-empty").mkdir()

    async def test_listing_shown_in_configured_zone(self):
        status, headers, data = await self._request("GET", "/public/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"report.txt", data)
        self.assertNotIn(b".hidden", data)

    async def test_listing_not_shown_outside_configured_zone(self):
        status, _, _ = await self._request("GET", "/other-empty/")
        self.assertEqual(status, 404)

    async def test_listing_entries_reference_the_reserved_icon_route(self):
        status, _, data = await self._request("GET", "/public/")
        self.assertEqual(status, 200)
        self.assertIn(b'src="/.omega-serv-icons/text-generic.svg"', data)

    async def test_icon_referenced_by_the_listing_is_actually_servable(self):
        status, headers, data = await self._request("GET", "/.omega-serv-icons/text-generic.svg")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertIn(b"<svg", data)


class TestIconRoute(_ServerTestBase):
    """Chemin reserve (meme statut que /healthz) - toujours actif, sans
    aucune option a activer (le directory listing lui-meme en depend)."""

    async def test_known_icon_is_servable_even_without_dirlisting_enabled(self):
        status, headers, data = await self._request("GET", "/.omega-serv-icons/folder.svg")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertIn(b"<svg", data)

    async def test_unknown_icon_name_is_404(self):
        status, _, _ = await self._request("GET", "/.omega-serv-icons/not-a-real-icon.svg")
        self.assertEqual(status, 404)


class TestIconRouteBypassesUserRules(_ServerTestBase):
    config_overrides: ClassVar[dict] = {
        "options": {"redirects": {
            "enabled": True,
            "list": [{"url_prefix": "/", "destination": "/index.html", "status_code": 301}],
        }},
    }

    async def test_icon_route_is_never_redirected(self):
        status, _, data = await self._request("GET", "/.omega-serv-icons/folder.svg")
        self.assertEqual(status, 200)
        self.assertIn(b"<svg", data)


class TestCacheControl(_ServerTestBase):
    config_overrides: ClassVar[dict] = {
        "options": {"cache": {
            "enabled": True,
            "default": "no-cache, must-revalidate",
            "extensions": {".html": "public, max-age=3600"},
        }},
    }

    async def test_cache_control_header_present(self):
        status, headers, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "public, max-age=3600")


class TestTrustedProxy(_ServerTestBase):
    config_overrides: ClassVar[dict] = {
        "options": {"trusted_proxy": {
            "enabled": True,
            "trusted_networks": ["127.0.0.1/32"],
            "header_preference": ["X-Forwarded-For"],
        }},
    }

    async def test_forwarded_for_honored_from_trusted_peer(self):
        await self._request("GET", "/index.html", headers={"X-Forwarded-For": "203.0.113.77"})
        access_log = (self.root / "var" / "log" / "access.log").read_text()
        self.assertIn("203.0.113.77", access_log)
        self.assertNotIn("127.0.0.1 - -", access_log)


if __name__ == "__main__":
    unittest.main()
