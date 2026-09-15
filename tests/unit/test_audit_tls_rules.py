# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.tls.entities import CertificateInfo
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.security.tls_rules import check_certificate_expiry

_NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


class _FakeClock:
    def now(self):
        return _NOW


class _FakeCertificateTool:
    def __init__(self, info):
        self._info = info

    def generate_self_signed(self, params, key_path, cert_path):
        raise NotImplementedError

    def inspect_certificate(self, cert_path):
        return self._info

    def keys_match(self, key_path, cert_path):
        return True


def _cert(not_after) -> CertificateInfo:
    return CertificateInfo(subject="CN=x", issuer="CN=x", not_before=_NOW - timedelta(days=1), not_after=not_after)


class TestCheckCertificateExpiry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        (self.project_root / "secure" / "certificates" / "server").mkdir(parents=True)
        self.cert_path = self.project_root / "secure" / "certificates" / "server" / "server.pem"
        self.cert_path.write_text("cert")

    def tearDown(self):
        self._tmp.cleanup()

    def _config(self, **overrides):
        tls = {"enabled": True, "mode": "direct"}
        tls.update(overrides)
        return OmegaServConfig.from_dict({"tls": tls})

    def test_tls_disabled_skips_check(self):
        config = self._config(enabled=False)
        tool = _FakeCertificateTool(_cert(_NOW + timedelta(days=5)))
        self.assertEqual(check_certificate_expiry(config, self.project_root, self.filesystem, tool, _FakeClock()), [])

    def test_behind_proxy_mode_skips_check(self):
        config = self._config(mode="behind_proxy")
        tool = _FakeCertificateTool(_cert(_NOW + timedelta(days=5)))
        self.assertEqual(check_certificate_expiry(config, self.project_root, self.filesystem, tool, _FakeClock()), [])

    def test_certificate_expiring_soon_flagged(self):
        config = self._config()
        tool = _FakeCertificateTool(_cert(_NOW + timedelta(days=10)))
        findings = check_certificate_expiry(config, self.project_root, self.filesystem, tool, _FakeClock())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "TLS-002")

    def test_certificate_far_from_expiry_not_flagged(self):
        config = self._config()
        tool = _FakeCertificateTool(_cert(_NOW + timedelta(days=200)))
        self.assertEqual(check_certificate_expiry(config, self.project_root, self.filesystem, tool, _FakeClock()), [])

    def test_already_expired_certificate_not_double_reported_here(self):
        # Deja rapporte en CRITICAL par la porte bloquante reexecutee
        # (CORE-ENV) - cette regle ne doit pas produire un second
        # finding pour la meme situation.
        config = self._config()
        tool = _FakeCertificateTool(_cert(_NOW - timedelta(days=1)))
        self.assertEqual(check_certificate_expiry(config, self.project_root, self.filesystem, tool, _FakeClock()), [])

    def test_missing_certificate_file_skips_check(self):
        self.cert_path.unlink()
        config = self._config()
        tool = _FakeCertificateTool(_cert(_NOW + timedelta(days=5)))
        self.assertEqual(check_certificate_expiry(config, self.project_root, self.filesystem, tool, _FakeClock()), [])


if __name__ == "__main__":
    unittest.main()
