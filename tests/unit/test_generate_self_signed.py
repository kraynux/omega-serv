import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.tls.generate_self_signed import generate_self_signed_certificate
from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeClock:
    def now(self):
        return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


class _FakeCertificateTool:
    def __init__(self):
        self.calls = []

    def generate_self_signed(self, params, key_path, cert_path):
        self.calls.append((params, key_path, cert_path))
        key_path.write_text("FAKE KEY")
        cert_path.write_text("FAKE CERT")

    def inspect_certificate(self, cert_path):
        raise NotImplementedError

    def keys_match(self, key_path, cert_path):
        raise NotImplementedError


class TestGenerateSelfSignedCertificate(unittest.TestCase):
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
        defaults = {"common_name": "localhost", "san_dns": ("localhost",)}
        defaults.update(overrides)
        return SelfSignedCertParams(**defaults)

    def test_invalid_params_rejected_before_calling_tool(self):
        result = generate_self_signed_certificate(
            self._params(common_name=""), self.root / "k.key", self.root / "c.pem",
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(result.success)
        self.assertEqual(self.tool.calls, [])

    def test_generates_files_with_correct_permissions(self):
        key_path = self.root / "server.key"
        cert_path = self.root / "server.pem"
        result = generate_self_signed_certificate(
            self._params(), key_path, cert_path, self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertTrue(result.success)
        self.assertEqual(self.filesystem.file_mode(key_path), 0o600)
        self.assertEqual(self.filesystem.file_mode(cert_path), 0o644)

    def test_backs_up_existing_files_before_overwrite(self):
        key_path = self.root / "server.key"
        cert_path = self.root / "server.pem"
        key_path.write_text("OLD KEY")
        cert_path.write_text("OLD CERT")

        generate_self_signed_certificate(
            self._params(), key_path, cert_path, self.tool, self.filesystem, self.clock, self.backups_dir,
        )

        backup_dir = self.backups_dir / "20260905-120000"
        self.assertEqual((backup_dir / "server.key").read_text(), "OLD KEY")
        self.assertEqual((backup_dir / "server.pem").read_text(), "OLD CERT")
        self.assertEqual(key_path.read_text(), "FAKE KEY")

    def test_no_backup_created_when_no_existing_files(self):
        key_path = self.root / "server.key"
        cert_path = self.root / "server.pem"
        generate_self_signed_certificate(
            self._params(), key_path, cert_path, self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(self.backups_dir.exists())


if __name__ == "__main__":
    unittest.main()
