import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.tls.sign_certificate_signing_request import (
    sign_certificate_signing_request,
)
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeClock:
    def now(self):
        return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


class _FakeCertificateTool:
    def __init__(self):
        self.sign_calls = []
        self.fullchain_calls = []

    def sign_csr(self, csr_path, ca_key_path, ca_cert_path, ca_key_password, serial_path, index_path, validity_days, out_cert_path):
        self.sign_calls.append((csr_path, ca_key_path, ca_cert_path, ca_key_password, validity_days))
        out_cert_path.write_text("FAKE SIGNED CERT")

    def build_fullchain(self, cert_path, ca_cert_path, fullchain_path):
        self.fullchain_calls.append((cert_path, ca_cert_path))
        fullchain_path.write_text("FAKE FULLCHAIN")


class TestSignCertificateSigningRequest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.tool = _FakeCertificateTool()
        self.clock = _FakeClock()
        self.backups_dir = self.root / "backups"
        self.csr = self.root / "server.csr"
        self.ca_key = self.root / "root-ca.key"
        self.ca_cert = self.root / "root-ca.pem"
        self.serial = self.root / "serial.txt"
        self.index = self.root / "index.txt"
        for p in (self.csr, self.ca_key, self.ca_cert):
            p.write_text("placeholder")

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_input_file_rejected_before_calling_tool(self):
        result = sign_certificate_signing_request(
            self.root / "missing.csr", self.ca_key, self.ca_cert, "capass",
            self.serial, self.index, 365, self.root / "out.pem",
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(result.success)
        self.assertEqual(self.tool.sign_calls, [])

    def test_invalid_validity_days_rejected(self):
        result = sign_certificate_signing_request(
            self.csr, self.ca_key, self.ca_cert, "capass", self.serial, self.index, 0, self.root / "out.pem",
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertFalse(result.success)
        self.assertEqual(self.tool.sign_calls, [])

    def test_signs_and_sets_permissions(self):
        out_cert = self.root / "server.pem"
        result = sign_certificate_signing_request(
            self.csr, self.ca_key, self.ca_cert, "capass", self.serial, self.index, 365, out_cert,
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        self.assertTrue(result.success)
        self.assertEqual(self.filesystem.file_mode(out_cert), 0o644)
        self.assertEqual(len(self.tool.sign_calls), 1)
        self.assertEqual(self.tool.fullchain_calls, [])

    def test_builds_fullchain_when_requested(self):
        out_cert = self.root / "server.pem"
        fullchain = self.root / "fullchain.pem"
        result = sign_certificate_signing_request(
            self.csr, self.ca_key, self.ca_cert, "capass", self.serial, self.index, 365, out_cert,
            self.tool, self.filesystem, self.clock, self.backups_dir, out_fullchain_path=fullchain,
        )
        self.assertTrue(result.success)
        self.assertEqual(self.filesystem.file_mode(fullchain), 0o644)
        self.assertEqual(len(self.tool.fullchain_calls), 1)

    def test_backs_up_existing_output_cert(self):
        out_cert = self.root / "server.pem"
        out_cert.write_text("OLD CERT")
        sign_certificate_signing_request(
            self.csr, self.ca_key, self.ca_cert, "capass", self.serial, self.index, 365, out_cert,
            self.tool, self.filesystem, self.clock, self.backups_dir,
        )
        backup_dir = self.backups_dir / "20260905-120000"
        self.assertEqual((backup_dir / "server.pem").read_text(), "OLD CERT")
        self.assertEqual(out_cert.read_text(), "FAKE SIGNED CERT")


if __name__ == "__main__":
    unittest.main()
