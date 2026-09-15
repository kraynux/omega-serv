# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.domain.security.tls.entities import CertificateInfo

_NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def _cert(subject="CN=localhost", issuer="CN=localhost", not_after=None):
    return CertificateInfo(
        subject=subject, issuer=issuer,
        not_before=_NOW - timedelta(days=1),
        not_after=not_after or (_NOW + timedelta(days=365)),
    )


class TestCertificateInfo(unittest.TestCase):
    def test_is_self_signed_when_subject_equals_issuer(self):
        self.assertTrue(_cert().is_self_signed)

    def test_not_self_signed_when_issuer_differs(self):
        self.assertFalse(_cert(issuer="CN=Some CA").is_self_signed)

    def test_is_expired_false_when_still_valid(self):
        self.assertFalse(_cert().is_expired(_NOW))

    def test_is_expired_true_when_past_not_after(self):
        expired = _cert(not_after=_NOW - timedelta(days=1))
        self.assertTrue(expired.is_expired(_NOW))

    def test_days_remaining(self):
        cert = _cert(not_after=_NOW + timedelta(days=30))
        self.assertEqual(cert.days_remaining(_NOW), 30)


if __name__ == "__main__":
    unittest.main()
