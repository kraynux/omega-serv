import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.route_request import route_request
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver


def _make_request(path: str, method: str = "GET", headers: list | None = None, body: bytes | None = None) -> HttpRequest:
    return HttpRequest(
        request_id="test-id",
        remote_ip="203.0.113.10",
        peer_ip="203.0.113.10",
        method=method,
        path=path,
        raw_path=path,
        query="",
        headers=HttpHeaders.from_pairs(headers or []),
        body=body,
        content_length=None,
        is_tls=False,
    )


class TestRouteRequest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        self.webroot = self.project_root / "webroot"
        self.webroot.mkdir()
        (self.webroot / "index.html").write_text("ok")
        self.filesystem = LocalFilesystem()
        self.resolver = SafePathResolver(self.filesystem, self.webroot)

    def tearDown(self):
        self._tmp.cleanup()

    async def _route(self, path: str, config: OmegaServConfig | None = None):
        return await route_request(
            _make_request(path), self.resolver, self.filesystem, config or OmegaServConfig(), self.project_root,
        )

    async def _route_request(self, request: HttpRequest, config: OmegaServConfig):
        return await route_request(request, self.resolver, self.filesystem, config, self.project_root)

    async def test_healthz_routes_to_healthz_handler(self):
        response = await self._route("/healthz")
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"OK")

    async def test_other_path_routes_to_static_handler(self):
        response = await self._route("/index.html")
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"ok")

    async def test_redirect_rule_takes_precedence(self):
        config = OmegaServConfig.from_dict({
            "options": {"redirects": {
                "enabled": True,
                "list": [{"url_prefix": "/old", "destination": "/new", "status_code": 301}],
            }},
        })
        response = await self._route("/old/page", config)
        self.assertEqual(response.status, HttpStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.headers["Location"], "/new")

    async def test_rewrite_changes_resolved_file(self):
        (self.webroot / "renamed.html").write_text("rewritten content")
        config = OmegaServConfig.from_dict({
            "options": {"rewrites": {
                "enabled": True,
                "list": [{"match_prefix": "/old.html", "replacement_prefix": "/renamed.html"}],
            }},
        })
        response = await self._route("/old.html", config)
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"rewritten content")

    async def test_rewrite_loop_returns_500(self):
        config = OmegaServConfig.from_dict({
            "options": {"rewrites": {
                "enabled": True,
                "list": [
                    {"match_prefix": "/a", "replacement_prefix": "/b"},
                    {"match_prefix": "/b", "replacement_prefix": "/a"},
                ],
            }},
        })
        response = await self._route("/a", config)
        self.assertEqual(response.status, HttpStatus.INTERNAL_SERVER_ERROR)

    async def test_alias_serves_from_target_outside_webroot(self):
        outside_dir = self.project_root / "shared-downloads"
        outside_dir.mkdir()
        (outside_dir / "file.txt").write_text("shared content")

        config = OmegaServConfig.from_dict({
            "options": {"aliases": {
                "enabled": True,
                "list": [{
                    "url_prefix": "/downloads/",
                    "target_path": "shared-downloads/",
                    "allow_outside_webroot": True,
                }],
            }},
        })
        response = await self._route("/downloads/file.txt", config)
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"shared content")

    async def test_alias_target_still_confined_to_its_own_root(self):
        outside_dir = self.project_root / "shared-downloads"
        outside_dir.mkdir()

        config = OmegaServConfig.from_dict({
            "options": {"aliases": {
                "enabled": True,
                "list": [{
                    "url_prefix": "/downloads/",
                    "target_path": "shared-downloads/",
                    "allow_outside_webroot": True,
                }],
            }},
        })
        response = await self._route("/downloads/../../secure/secret.txt", config)
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)

    async def test_post_to_upload_zone_stores_file(self):
        config = OmegaServConfig.from_dict({
            "options": {"upload": {
                "enabled": True,
                "zones": [{"url_prefix": "/upload/", "storage_path": "var/uploads/public"}],
            }},
        })
        boundary = "----test"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="photo.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
            "BINARY"
            f"\r\n--{boundary}--\r\n"
        ).encode()
        request = _make_request(
            "/upload/", method="POST",
            headers=[("Content-Type", f"multipart/form-data; boundary={boundary}")],
            body=body,
        )
        response = await self._route_request(request, config)
        self.assertEqual(response.status, 201)
        stored = list((self.project_root / "var" / "uploads" / "public").iterdir())
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].read_bytes(), b"BINARY")

    async def test_get_to_upload_zone_falls_through_to_static_handler(self):
        (self.webroot / "upload").mkdir()
        (self.webroot / "upload" / "index.html").write_text("listing")
        config = OmegaServConfig.from_dict({
            "options": {"upload": {
                "enabled": True,
                "zones": [{"url_prefix": "/upload/", "storage_path": "var/uploads/public"}],
            }},
        })
        response = await self._route_request(_make_request("/upload/index.html"), config)
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"listing")

    async def test_disabled_upload_option_post_falls_through(self):
        config = OmegaServConfig.from_dict({
            "options": {"upload": {
                "enabled": False,
                "zones": [{"url_prefix": "/upload/", "storage_path": "var/uploads/public"}],
            }},
        })
        request = _make_request("/upload/", method="POST", body=b"")
        response = await self._route_request(request, config)
        self.assertEqual(response.status, HttpStatus.METHOD_NOT_ALLOWED)

    async def test_disabled_options_are_ignored(self):
        config = OmegaServConfig.from_dict({
            "options": {"redirects": {
                "enabled": False,
                "list": [{"url_prefix": "/index.html", "destination": "/elsewhere"}],
            }},
        })
        response = await self._route("/index.html", config)
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"ok")


if __name__ == "__main__":
    unittest.main()
