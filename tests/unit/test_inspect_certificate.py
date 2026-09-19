import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.tls.inspect_certificate import inspect_certificate_report
from omega_serv.domain.security.tls.entities import CertificateInfo
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

_NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


class _FakeClock:
    def now(self):
        return _NOW


class _FakeCertificateTool:
    def __init__(self, info, keys_match=True):
        self._info = info
        self._keys_match = keys_match

    def generate_self_signed(self, params, key_path, cert_path):
        raise NotImplementedError

    def inspect_certificate(self, cert_path):
        return self._info

    def keys_match(self, key_path, cert_path):
        return self._keys_match


def _cert(not_after=None):
    return CertificateInfo(
        subject="CN=localhost", issuer="CN=localhost",
        not_before=_NOW - timedelta(days=1), not_after=not_after or (_NOW + timedelta(days=100)),
    )


class TestInspectCertificateReport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.clock = _FakeClock()

    def tearDown(self):
        self._tmp.cleanup()

    def test_healthy_certificate_report(self):
        key_path = self.root / "server.key"
        key_path.write_text("key")
        key_path.chmod(0o600)
        cert_path = self.root / "server.pem"

        report = inspect_certificate_report(cert_path, key_path, _FakeCertificateTool(_cert()), self.filesystem, self.clock)
        self.assertFalse(report.is_expired)
        self.assertTrue(report.key_matches)
        self.assertEqual(report.key_mode, 0o600)
        self.assertFalse(report.expiring_soon)

    def test_missing_key_file_reports_none_for_key_fields(self):
        cert_path = self.root / "server.pem"
        report = inspect_certificate_report(cert_path, self.root / "missing.key", _FakeCertificateTool(_cert()), self.filesystem, self.clock)
        self.assertIsNone(report.key_matches)
        self.assertIsNone(report.key_mode)

    def test_expired_certificate_flagged(self):
        cert_path = self.root / "server.pem"
        expired = _cert(not_after=_NOW - timedelta(days=1))
        report = inspect_certificate_report(cert_path, self.root / "k.key", _FakeCertificateTool(expired), self.filesystem, self.clock)
        self.assertTrue(report.is_expired)

    def test_expiring_soon_flagged_under_warn_days(self):
        cert_path = self.root / "server.pem"
        soon = _cert(not_after=_NOW + timedelta(days=10))
        report = inspect_certificate_report(cert_path, self.root / "k.key", _FakeCertificateTool(soon), self.filesystem, self.clock, warn_days=30)
        self.assertTrue(report.expiring_soon)

    def test_not_expiring_soon_above_warn_days(self):
        cert_path = self.root / "server.pem"
        far = _cert(not_after=_NOW + timedelta(days=200))
        report = inspect_certificate_report(cert_path, self.root / "k.key", _FakeCertificateTool(far), self.filesystem, self.clock, warn_days=30)
        self.assertFalse(report.expiring_soon)


if __name__ == "__main__":
    unittest.main()
