import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.tls.import_certificate import import_certificate
from omega_serv.domain.security.tls.entities import CertificateInfo
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeClock:
    def now(self):
        return datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)


class _FakeCertificateTool:
    def __init__(self, keys_match=True, is_expired=False):
        self._keys_match = keys_match
        self._is_expired = is_expired
        self.inspect_calls = []
        self.keys_match_calls = []

    def inspect_certificate(self, cert_path):
        self.inspect_calls.append(cert_path)
        now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
        not_after = now - timedelta(days=1) if self._is_expired else now + timedelta(days=60)
        return CertificateInfo(
            subject="CN=example.dynu.com", issuer="CN=Let's Encrypt",
            not_before=now - timedelta(days=1), not_after=not_after,
        )

    def keys_match(self, key_path, cert_path):
        self.keys_match_calls.append((key_path, cert_path))
        return self._keys_match

    def build_fullchain(self, cert_path, ca_cert_path, fullchain_path):
        fullchain_path.parent.mkdir(parents=True, exist_ok=True)
        fullchain_path.write_text(cert_path.read_text() + ca_cert_path.read_text())

    def generate_self_signed(self, *args, **kwargs):
        raise NotImplementedError


class TestImportCertificate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.clock = _FakeClock()
        self.backups_dir = self.root / "backups"
        self.source_key = self.root / "source" / "privkey.pem"
        self.source_cert = self.root / "source" / "fullchain.pem"
        self.source_key.parent.mkdir(parents=True)
        self.source_key.write_text("SOURCE KEY")
        self.source_cert.write_text("SOURCE CERT")
        self.dest_key = self.root / "secure" / "server.key"
        self.dest_cert = self.root / "secure" / "server.pem"

    def tearDown(self):
        self._tmp.cleanup()

    def _import(self, tool=None):
        return import_certificate(
            self.source_key, self.source_cert, self.dest_key, self.dest_cert,
            tool or _FakeCertificateTool(), self.filesystem, self.clock, self.backups_dir,
        )

    def test_missing_source_key_rejected(self):
        self.source_key.unlink()
        result = self._import()
        self.assertFalse(result.success)
        self.assertIn("cle privee source", result.message)
        self.assertFalse(self.dest_cert.exists())

    def test_missing_source_cert_rejected(self):
        self.source_cert.unlink()
        result = self._import()
        self.assertFalse(result.success)
        self.assertIn("certificat source", result.message)

    def test_mismatched_key_and_certificate_rejected(self):
        result = self._import(tool=_FakeCertificateTool(keys_match=False))
        self.assertFalse(result.success)
        self.assertIn("ne correspondent pas", result.message)
        self.assertFalse(self.dest_cert.exists())

    def test_expired_certificate_rejected(self):
        result = self._import(tool=_FakeCertificateTool(is_expired=True))
        self.assertFalse(result.success)
        self.assertIn("expire", result.message)

    def test_successful_import_copies_files_with_correct_permissions(self):
        result = self._import()
        self.assertTrue(result.success)
        self.assertEqual(self.dest_key.read_text(), "SOURCE KEY")
        self.assertEqual(self.dest_cert.read_text(), "SOURCE CERT")
        self.assertEqual(self.filesystem.file_mode(self.dest_key), 0o600)
        self.assertEqual(self.filesystem.file_mode(self.dest_cert), 0o644)

    def test_backs_up_existing_destination_before_overwrite(self):
        self.dest_key.parent.mkdir(parents=True)
        self.dest_key.write_text("OLD KEY")
        self.dest_cert.write_text("OLD CERT")

        self._import()

        backup_dir = self.backups_dir / "20260918-120000"
        self.assertEqual((backup_dir / "server.key").read_text(), "OLD KEY")
        self.assertEqual((backup_dir / "server.pem").read_text(), "OLD CERT")
        self.assertEqual(self.dest_key.read_text(), "SOURCE KEY")

    def test_no_backup_created_when_no_existing_destination(self):
        self._import()
        self.assertFalse(self.backups_dir.exists())

    def test_chain_concatenated_into_destination_certificate_when_provided(self):
        source_chain = self.root / "source" / "chain.pem"
        source_chain.write_text("SOURCE CHAIN")

        result = import_certificate(
            self.source_key, self.source_cert, self.dest_key, self.dest_cert,
            _FakeCertificateTool(), self.filesystem, self.clock, self.backups_dir,
            source_chain_path=source_chain,
        )

        self.assertTrue(result.success)
        self.assertEqual(self.dest_cert.read_text(), "SOURCE CERTSOURCE CHAIN")
        self.assertEqual(self.filesystem.file_mode(self.dest_cert), 0o644)

    def test_missing_declared_chain_rejected(self):
        source_chain = self.root / "source" / "missing-chain.pem"

        result = import_certificate(
            self.source_key, self.source_cert, self.dest_key, self.dest_cert,
            _FakeCertificateTool(), self.filesystem, self.clock, self.backups_dir,
            source_chain_path=source_chain,
        )

        self.assertFalse(result.success)
        self.assertIn("chaine intermediaire", result.message)


if __name__ == "__main__":
    unittest.main()
