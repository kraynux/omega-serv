import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.tls.request_lets_encrypt_certificate import (
    request_lets_encrypt_certificate,
)
from omega_serv.domain.security.tls.entities import CertificateInfo
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.ports.process_runner_port import ProcessResult


class _FakeClock:
    def now(self):
        return datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)


class _FakeCertificateTool:
    def inspect_certificate(self, cert_path):
        now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
        return CertificateInfo(
            subject="CN=example.dynu.com", issuer="CN=Let's Encrypt",
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=89),
        )

    def keys_match(self, key_path, cert_path):
        return True

    def build_fullchain(self, cert_path, ca_cert_path, fullchain_path):
        raise NotImplementedError


class _FakeProcessRunner:
    def __init__(self, returncode=0, stdout="", stderr="", side_effect=None):
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._side_effect = side_effect
        self.calls = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append((args, timeout))
        if self._side_effect is not None:
            self._side_effect(args)
        return ProcessResult(returncode=self._returncode, stdout=self._stdout, stderr=self._stderr)

    def run_interactive(self, args):
        raise NotImplementedError


class TestRequestLetsEncryptCertificate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.clock = _FakeClock()
        self.tool = _FakeCertificateTool()
        self.webroot = self.root / "webroot"
        self.webroot.mkdir()
        self.letsencrypt_dir = self.root / "secure" / "certificates" / "letsencrypt"
        self.dest_key = self.root / "secure" / "certificates" / "server" / "server.key"
        self.dest_cert = self.root / "secure" / "certificates" / "server" / "server.pem"
        self.backups_dir = self.root / "var" / "backups" / "certificates"
        self.domain = "example.dynu.com"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_fake_certbot_output(self, args):
        live_dir = self.letsencrypt_dir / "config" / "live" / self.domain
        live_dir.mkdir(parents=True, exist_ok=True)
        (live_dir / "privkey.pem").write_text("FAKE KEY")
        (live_dir / "fullchain.pem").write_text("FAKE CERT")

    def _request(self, runner=None, **overrides):
        runner = runner or _FakeProcessRunner(side_effect=self._write_fake_certbot_output)
        kwargs = {
            "domain": self.domain, "webroot_path": self.webroot,
            "letsencrypt_dir": self.letsencrypt_dir,
            "dest_key_path": self.dest_key, "dest_cert_path": self.dest_cert,
            "service_name": "omega-serv", "python_executable": "/x/python3",
            "process_runner": runner, "certificate_tool": self.tool,
            "filesystem": self.filesystem, "clock": self.clock, "backups_dir": self.backups_dir,
        }
        kwargs.update(overrides)
        return runner, request_lets_encrypt_certificate(**kwargs)

    def test_rejects_empty_domain_before_touching_anything(self):
        runner, result = self._request(domain="")
        self.assertFalse(result.success)
        self.assertEqual(runner.calls, [])

    def test_never_targets_system_letsencrypt_directory(self):
        runner, _result = self._request()
        argv = runner.calls[0][0]
        self.assertNotIn("/etc/letsencrypt", " ".join(argv))
        self.assertIn(str(self.letsencrypt_dir), " ".join(argv))

    def test_writes_the_hook_script_before_calling_certbot(self):
        runner, _result = self._request()
        hook_path = self.letsencrypt_dir / "hooks" / f"deploy-{self.domain}.sh"
        self.assertTrue(hook_path.exists())
        self.assertEqual(oct(hook_path.stat().st_mode & 0o777), "0o700")
        argv = runner.calls[0][0]
        self.assertIn(str(hook_path), argv)

    def test_successful_flow_installs_the_certificate(self):
        _runner, result = self._request()
        self.assertTrue(result.success)
        self.assertEqual(self.dest_cert.read_text(), "FAKE CERT")
        self.assertEqual(self.filesystem.file_mode(self.dest_key), 0o600)

    def test_certbot_failure_reported_without_importing_anything(self):
        failing_runner = _FakeProcessRunner(returncode=1, stderr="rate limited")
        _runner, result = self._request(runner=failing_runner)
        self.assertFalse(result.success)
        self.assertIn("rate limited", result.message)
        self.assertFalse(self.dest_cert.exists())

    def test_import_failure_after_successful_certbot_is_reported_distinctly(self):
        runner = _FakeProcessRunner()  # side_effect absent : aucun fichier ecrit
        _runner, result = self._request(runner=runner)
        self.assertFalse(result.success)
        self.assertIn("import echoue", result.message)

    def test_staging_defaults_to_true(self):
        runner, _result = self._request()
        argv = runner.calls[0][0]
        self.assertIn("--staging", argv)

    def test_staging_can_be_disabled_explicitly(self):
        runner, _result = self._request(staging=False)
        argv = runner.calls[0][0]
        self.assertNotIn("--staging", argv)


if __name__ == "__main__":
    unittest.main()
