import tempfile
import unittest
from pathlib import Path

from omega_serv.application.tls.revoke_certificate import revoke_certificate
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeCertificateTool:
    def __init__(self):
        self.calls = []

    def revoke_certificate(self, cert_path, ca_key_path, ca_cert_path, ca_key_password, index_path):
        self.calls.append((cert_path, ca_key_path, ca_cert_path, ca_key_password, index_path))


class TestRevokeCertificate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.tool = _FakeCertificateTool()
        self.cert = self.root / "server.pem"
        self.ca_key = self.root / "root-ca.key"
        self.ca_cert = self.root / "root-ca.pem"
        self.index = self.root / "index.txt"
        for p in (self.cert, self.ca_key, self.ca_cert, self.index):
            p.write_text("placeholder")

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_input_file_rejected_before_calling_tool(self):
        result = revoke_certificate(
            self.root / "missing.pem", self.ca_key, self.ca_cert, "capass", self.index, self.tool, self.filesystem,
        )
        self.assertFalse(result.success)
        self.assertEqual(self.tool.calls, [])

    def test_revokes_when_all_files_present(self):
        result = revoke_certificate(
            self.cert, self.ca_key, self.ca_cert, "capass", self.index, self.tool, self.filesystem,
        )
        self.assertTrue(result.success)
        self.assertEqual(len(self.tool.calls), 1)


if __name__ == "__main__":
    unittest.main()
