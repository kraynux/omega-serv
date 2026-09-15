# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste l'adaptateur openssl reel (pas de mock) - meme discipline que
test_json_config_repository.py : I/O reelle (ici, un vrai processus
openssl) contre un dossier temporaire."""
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.security.tls.entities import CaParams, CsrParams, SelfSignedCertParams
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

_OPENSSL_MISSING = shutil.which("openssl") is None


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestOpensslCertificateTool(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.tool = OpensslCertificateTool(SubprocessRunner())

    def tearDown(self):
        self._tmp.cleanup()

    _generate_counter = 0

    def _generate(self, **overrides):
        defaults = {"common_name": "localhost", "san_dns": ("localhost",), "san_ip": ("127.0.0.1",), "validity_days": 365}
        defaults.update(overrides)
        params = SelfSignedCertParams(**defaults)
        TestOpensslCertificateTool._generate_counter += 1
        n = TestOpensslCertificateTool._generate_counter
        key_path = self.root / f"server-{n}.key"
        cert_path = self.root / f"server-{n}.pem"
        self.tool.generate_self_signed(params, key_path, cert_path)
        return key_path, cert_path

    def test_generates_key_and_cert_files(self):
        key_path, cert_path = self._generate()
        self.assertTrue(key_path.is_file())
        self.assertTrue(cert_path.is_file())

    def test_generated_cert_is_self_signed(self):
        _, cert_path = self._generate()
        info = self.tool.inspect_certificate(cert_path)
        self.assertTrue(info.is_self_signed)

    def test_generated_cert_has_expected_cn_and_san(self):
        _, cert_path = self._generate(common_name="example.internal", san_dns=("example.internal", "www.example.internal"), san_ip=("10.0.0.1",))
        info = self.tool.inspect_certificate(cert_path)
        self.assertIn("CN=example.internal", info.subject)
        self.assertIn("example.internal", info.san_dns)
        self.assertIn("www.example.internal", info.san_dns)
        self.assertIn("10.0.0.1", info.san_ip)

    def test_generated_cert_validity_matches_requested_days(self):
        _, cert_path = self._generate(validity_days=30)
        info = self.tool.inspect_certificate(cert_path)
        now = datetime.now(timezone.utc)
        self.assertLessEqual(info.days_remaining(now), 30)
        self.assertGreaterEqual(info.days_remaining(now), 29)

    def test_rsa4096_key_type(self):
        _, cert_path = self._generate(key_type="rsa4096")
        info = self.tool.inspect_certificate(cert_path)
        self.assertEqual(info.key_bits, 4096)

    def test_ecdsa_p256_key_type(self):
        _, cert_path = self._generate(key_type="ecdsa-p256")
        info = self.tool.inspect_certificate(cert_path)
        self.assertEqual(info.key_bits, 256)

    def test_matching_key_and_cert_detected(self):
        key_path, cert_path = self._generate()
        self.assertTrue(self.tool.keys_match(key_path, cert_path))

    def test_mismatched_key_and_cert_detected(self):
        key_path, _ = self._generate()
        _, other_cert_path = self._generate(common_name="other.internal", san_dns=("other.internal",))
        self.assertFalse(self.tool.keys_match(key_path, other_cert_path))

    def test_inspect_missing_certificate_raises(self):
        with self.assertRaises(CertificateToolError):
            self.tool.inspect_certificate(self.root / "does-not-exist.pem")


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestOpensslCertificateToolCaLocale(unittest.TestCase):
    """CA locale (6b, doc TLS §7) - meme discipline que la classe
    ci-dessus : vrais appels openssl contre un dossier temporaire."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.tool = OpensslCertificateTool(SubprocessRunner())
        self.ca_key = self.root / "ca" / "root-ca.key"
        self.ca_cert = self.root / "ca" / "root-ca.pem"
        self.serial = self.root / "ca" / "serial.txt"
        self.index = self.root / "ca" / "index.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def _generate_ca(self, **overrides):
        defaults = {"common_name": "Test CA", "key_password": "capass123"}
        defaults.update(overrides)
        self.tool.generate_ca(CaParams(**defaults), self.ca_key, self.ca_cert, self.serial, self.index)

    def _generate_and_sign(self, days=365, **csr_overrides):
        defaults = {"common_name": "test.local", "san_dns": ("test.local",), "san_ip": ("127.0.0.1",)}
        defaults.update(csr_overrides)
        server_key = self.root / "server.key"
        server_csr = self.root / "server.csr"
        server_cert = self.root / "server.pem"
        self.tool.generate_csr(CsrParams(**defaults), server_key, server_csr)
        self.tool.sign_csr(server_csr, self.ca_key, self.ca_cert, "capass123", self.serial, self.index, days, server_cert)
        return server_key, server_cert

    def test_generate_ca_creates_key_cert_serial_index(self):
        self._generate_ca()
        self.assertTrue(self.ca_key.is_file())
        self.assertTrue(self.ca_cert.is_file())
        self.assertTrue(self.serial.is_file())
        self.assertTrue(self.index.is_file())
        self.assertEqual(self.serial.read_text().strip(), "1000")
        self.assertEqual(self.index.read_text(), "")

    def test_generated_ca_cert_is_self_signed_with_ca_true(self):
        self._generate_ca()
        info = self.tool.inspect_certificate(self.ca_cert)
        self.assertTrue(info.is_self_signed)

    def test_generate_csr_creates_key_and_csr_files(self):
        server_key = self.root / "server.key"
        server_csr = self.root / "server.csr"
        self.tool.generate_csr(CsrParams(common_name="test.local", san_dns=("test.local",)), server_key, server_csr)
        self.assertTrue(server_key.is_file())
        self.assertTrue(server_csr.is_file())

    def test_sign_csr_produces_cert_signed_by_ca_with_san_copied(self):
        self._generate_ca()
        _, server_cert = self._generate_and_sign()
        info = self.tool.inspect_certificate(server_cert)
        self.assertFalse(info.is_self_signed)
        self.assertIn("CN=Test CA", info.issuer)
        self.assertIn("test.local", info.san_dns)
        self.assertIn("127.0.0.1", info.san_ip)

    def test_sign_csr_increments_serial(self):
        self._generate_ca()
        self._generate_and_sign()
        self.assertEqual(self.serial.read_text().strip(), "1001")

    def test_sign_csr_appends_index_entry(self):
        self._generate_ca()
        self._generate_and_sign()
        lines = self.index.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("V\t"))
        self.assertIn("1001", lines[0])

    def test_build_fullchain_concatenates_server_and_ca(self):
        self._generate_ca()
        _, server_cert = self._generate_and_sign()
        fullchain = self.root / "fullchain.pem"
        self.tool.build_fullchain(server_cert, self.ca_cert, fullchain)
        content = fullchain.read_text()
        self.assertEqual(content, server_cert.read_text() + self.ca_cert.read_text())

    def test_signed_certificate_verifies_against_ca(self):
        self._generate_ca()
        _, server_cert = self._generate_and_sign()
        # Verification independante via openssl directement (pas via le
        # tool lui-meme) - preuve que la chaine de confiance fonctionne
        # reellement, pas seulement que les fichiers existent.
        result = SubprocessRunner().run(["openssl", "verify", "-CAfile", str(self.ca_cert), str(server_cert)])
        self.assertTrue(result.ok, result.stderr)

    def test_revoke_certificate_marks_index_entry_revoked(self):
        self._generate_ca()
        _, server_cert = self._generate_and_sign()
        self.tool.revoke_certificate(server_cert, self.ca_key, self.ca_cert, "capass123", self.index)
        line = self.index.read_text().splitlines()[0]
        fields = line.split("\t")
        self.assertEqual(fields[0], "R")
        self.assertNotEqual(fields[2], "")

    def test_revoke_certificate_not_signed_by_ca_raises(self):
        self._generate_ca()
        unrelated_key = self.root / "unrelated.key"
        unrelated_cert = self.root / "unrelated.pem"
        self.tool.generate_self_signed(
            SelfSignedCertParams(common_name="unrelated.local", san_dns=("unrelated.local",)),
            unrelated_key, unrelated_cert,
        )
        with self.assertRaises(CertificateToolError):
            self.tool.revoke_certificate(unrelated_cert, self.ca_key, self.ca_cert, "capass123", self.index)


if __name__ == "__main__":
    unittest.main()
