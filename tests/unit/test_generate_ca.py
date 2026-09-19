import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.tls.generate_ca_certificate import generate_ca_certificate
from omega_serv.domain.security.tls.entities import CaParams
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeClock:
    def now(self):
        return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


class _FakeCertificateTool:
    def __init__(self):
        self.calls = []

    def generate_ca(self, params, key_path, cert_path, serial_path, index_path):
        self.calls.append((params, key_path, cert_path, serial_path, index_path))
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("FAKE CA KEY")
        cert_path.write_text("FAKE CA CERT")
        serial_path.write_text("1000\n")
        index_path.write_text("")


class TestGenerateCaCertificate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.tool = _FakeCertificateTool()
        self.clock = _FakeClock()
        self.backups_dir = self.root / "backups"
        self.ca_dir = self.root / "ca"

    def tearDown(self):
        self._tmp.cleanup()

    def _params(self, **overrides):
        defaults = {"common_name": "Test CA", "key_password": "capass123"}
        defaults.update(overrides)
        return CaParams(**defaults)

    def _paths(self):
        return (self.ca_dir / "root-ca.key", self.ca_dir / "root-ca.pem", self.ca_dir / "serial.txt", self.ca_dir / "index.txt")

    def test_invalid_params_rejected_before_calling_tool(self):
        key, cert, serial, index = self._paths()
        result = generate_ca_certificate(
            self._params(common_name=""), key, cert, serial, index,
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(result.success)
        self.assertEqual(self.tool.calls, [])

    def test_missing_passphrase_rejected(self):
        key, cert, serial, index = self._paths()
        result = generate_ca_certificate(
            self._params(key_password=""), key, cert, serial, index,
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(result.success)
        self.assertIn("key_password", result.message)
        self.assertEqual(self.tool.calls, [])

    def test_generates_files_with_correct_permissions(self):
        key, cert, serial, index = self._paths()
        result = generate_ca_certificate(
            self._params(), key, cert, serial, index, self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertTrue(result.success)
        self.assertEqual(self.filesystem.file_mode(key), 0o600)
        self.assertEqual(self.filesystem.file_mode(cert), 0o644)
        self.assertEqual(self.filesystem.file_mode(serial), 0o600)
        self.assertEqual(self.filesystem.file_mode(index), 0o600)

    def test_ca_directory_created_with_0700(self):
        key, cert, serial, index = self._paths()
        generate_ca_certificate(
            self._params(), key, cert, serial, index, self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertEqual(self.filesystem.file_mode(self.ca_dir), 0o700)

    def test_backs_up_existing_files_before_overwrite(self):
        key, cert, serial, index = self._paths()
        key.parent.mkdir(parents=True)
        key.write_text("OLD KEY")
        cert.write_text("OLD CERT")

        generate_ca_certificate(
            self._params(), key, cert, serial, index, self.tool, self.filesystem, self.clock, self.backups_dir,
        )

        backup_dir = self.backups_dir / "20260905-120000"
        self.assertEqual((backup_dir / "root-ca.key").read_text(), "OLD KEY")
        self.assertEqual((backup_dir / "root-ca.pem").read_text(), "OLD CERT")
        self.assertEqual(key.read_text(), "FAKE CA KEY")


if __name__ == "__main__":
    unittest.main()
