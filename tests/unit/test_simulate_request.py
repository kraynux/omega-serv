# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.simulate_request import simulate_request
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver


class TestSimulateRequest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        self.webroot = self.project_root / "webroot"
        self.webroot.mkdir()
        (self.webroot / "index.html").write_text("ok")
        (self.webroot / ".env").write_text("secret")
        self.filesystem = LocalFilesystem()
        self.resolver = SafePathResolver(self.filesystem, self.webroot)
        self.config = OmegaServConfig()

    def tearDown(self):
        self._tmp.cleanup()

    async def test_existing_file(self):
        report = await simulate_request("GET", "/index.html", self.config, self.resolver, self.filesystem, self.project_root)
        self.assertEqual(report.normalized_path, "/index.html")
        self.assertTrue(report.method_allowed)
        self.assertFalse(report.denied_by_access_policy)
        self.assertTrue(report.file_exists)
        self.assertEqual(report.response_status, 200)
        self.assertIn("Content-Security-Policy", report.response_headers)

    async def test_missing_file(self):
        report = await simulate_request("GET", "/nope.html", self.config, self.resolver, self.filesystem, self.project_root)
        self.assertEqual(report.response_status, 404)
        self.assertFalse(report.file_exists)

    async def test_dotfile_denied(self):
        report = await simulate_request("GET", "/.env", self.config, self.resolver, self.filesystem, self.project_root)
        self.assertTrue(report.denied_by_access_policy)
        self.assertEqual(report.response_status, 403)

    async def test_traversal_rejected(self):
        report = await simulate_request("GET", "/../secure/x", self.config, self.resolver, self.filesystem, self.project_root)
        self.assertIsNone(report.normalized_path)
        self.assertEqual(report.rejection_reason, "TRAVERSAL_ATTEMPT")
        self.assertEqual(report.response_status, 403)

    async def test_disallowed_method(self):
        report = await simulate_request("POST", "/index.html", self.config, self.resolver, self.filesystem, self.project_root)
        self.assertFalse(report.method_allowed)
        self.assertEqual(report.response_status, 405)


if __name__ == "__main__":
    unittest.main()
