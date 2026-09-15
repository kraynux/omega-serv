# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.tls.generate_certificate_signing_request import (
    generate_certificate_signing_request,
)
from omega_serv.domain.security.tls.entities import CsrParams
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeClock:
    def now(self):
        return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


class _FakeCertificateTool:
    def __init__(self):
        self.calls = []

    def generate_csr(self, params, key_path, csr_path):
        self.calls.append((params, key_path, csr_path))
        key_path.write_text("FAKE KEY")
        csr_path.write_text("FAKE CSR")


class TestGenerateCertificateSigningRequest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.tool = _FakeCertificateTool()
        self.clock = _FakeClock()
        self.backups_dir = self.root / "backups"

    def tearDown(self):
        self._tmp.cleanup()

    def _params(self, **overrides):
        defaults = {"common_name": "test.local", "san_dns": ("test.local",)}
        defaults.update(overrides)
        return CsrParams(**defaults)

    def test_invalid_params_rejected_before_calling_tool(self):
        result = generate_certificate_signing_request(
            self._params(common_name=""), self.root / "k.key", self.root / "c.csr",
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(result.success)
        self.assertEqual(self.tool.calls, [])

    def test_missing_san_rejected(self):
        result = generate_certificate_signing_request(
            self._params(san_dns=()), self.root / "k.key", self.root / "c.csr",
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(result.success)
        self.assertEqual(self.tool.calls, [])

    def test_generates_files_with_correct_permissions(self):
        key_path = self.root / "server.key"
        csr_path = self.root / "server.csr"
        result = generate_certificate_signing_request(
            self._params(), key_path, csr_path, self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertTrue(result.success)
        self.assertEqual(self.filesystem.file_mode(key_path), 0o600)
        self.assertEqual(self.filesystem.file_mode(csr_path), 0o644)


if __name__ == "__main__":
    unittest.main()
