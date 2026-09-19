import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.security.run_audit import run_audit
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class _FakeClock:
    def now(self):
        return datetime(2026, 9, 6, tzinfo=timezone.utc)


class _UnusedCertificateTool:
    """N'est jamais cense etre appele quand TLS est desactive - toute
    invocation fait echouer le test bruyamment plutot que de retourner
    un resultat silencieusement faux."""

    def generate_self_signed(self, params, key_path, cert_path):
        raise AssertionError("ne devrait jamais etre appele : TLS desactive")

    def inspect_certificate(self, cert_path):
        raise AssertionError("ne devrait jamais etre appele : TLS desactive")

    def keys_match(self, key_path, cert_path):
        raise AssertionError("ne devrait jamais etre appele : TLS desactive")


class TestRunAudit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "webroot").mkdir()
        self.filesystem = LocalFilesystem()
        self.clock = _FakeClock()
        self.certificate_tool = _UnusedCertificateTool()

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, config: OmegaServConfig, **kwargs):
        return run_audit(
            config, Path("config/omega-serve.json"), self.project_root,
            self.filesystem, self.certificate_tool, self.clock, **kwargs,
        )

    def test_default_config_is_secure(self):
        result = self._run(OmegaServConfig())
        self.assertTrue(result.is_secure)
        self.assertEqual(result.exit_code, 0)

    def test_hsts_without_tls_reported_as_core_env_critical(self):
        config = OmegaServConfig.from_dict({"security": {"hsts_enabled": True}})
        result = self._run(config)
        core_findings = [f for f in result.findings if f.rule_id == "CORE-STRUCT"]
        self.assertTrue(any("hsts_enabled" in f.message for f in core_findings))
        self.assertEqual(result.exit_code, 1)

    def test_pure_rule_finding_present(self):
        config = OmegaServConfig.from_dict({"server": {"bind": "0.0.0.0"}})
        result = self._run(config)
        self.assertTrue(any(f.rule_id == "TLS-003" for f in result.findings))

    def test_permission_rule_finding_present(self):
        auth_file = self.project_root / "secure" / "auth" / "users.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("{}")
        auth_file.chmod(0o644)
        config = OmegaServConfig.from_dict({"options": {"auth": {"enabled": True}}})
        result = self._run(config)
        self.assertTrue(any(f.rule_id == "PERM-002" for f in result.findings))

    def test_service_unit_check_skipped_when_no_path_given(self):
        result = self._run(OmegaServConfig(), service_unit_path=None)
        self.assertEqual([f for f in result.findings if f.rule_id == "SVC-001"], [])

    def test_service_unit_check_runs_when_path_given(self):
        unit_path = self.project_root / "omega-serv.service"
        unit_path.write_text("[Service]\nExecStart=x\n")
        result = self._run(OmegaServConfig(), service_unit_path=unit_path)
        self.assertTrue(any(f.rule_id == "SVC-001" for f in result.findings))

    def test_upload_rule_finding_present(self):
        config = OmegaServConfig.from_dict({"options": {"upload": {
            "enabled": True,
            "zones": [{"url_prefix": "/upload/", "storage_path": "var/uploads/public"}],
        }}})
        result = self._run(config)
        self.assertTrue(any(f.rule_id == "UPLOAD-001" for f in result.findings))

    def test_proxy_upstream_tls_unverified_rule_finding_present(self):
        config = OmegaServConfig.from_dict({"options": {"reverse_proxy": {
            "enabled": True,
            "zones": [{
                "url_prefix": "/api/",
                "upstreams": [{"host": "10.0.0.5", "port": 8443, "use_tls": True}],
                "verify_upstream_tls": False,
            }],
        }}})
        result = self._run(config)
        self.assertTrue(any(f.rule_id == "PROXY-001" for f in result.findings))

    def test_proxy_upstream_tls_rule_absent_when_verification_enabled(self):
        config = OmegaServConfig.from_dict({"options": {"reverse_proxy": {
            "enabled": True,
            "zones": [{
                "url_prefix": "/api/",
                "upstreams": [{"host": "10.0.0.5", "port": 8443, "use_tls": True}],
            }],
        }}})
        result = self._run(config)
        self.assertFalse(any(f.rule_id == "PROXY-001" for f in result.findings))

    def test_proxy_upstream_tls_rule_absent_for_http_only_zone(self):
        config = OmegaServConfig.from_dict({"options": {"reverse_proxy": {
            "enabled": True,
            "zones": [{
                "url_prefix": "/api/",
                "upstreams": [{"host": "10.0.0.5", "port": 8080}],
                "verify_upstream_tls": False,
            }],
        }}})
        result = self._run(config)
        self.assertFalse(any(f.rule_id == "PROXY-001" for f in result.findings))

    def test_waf_log_only_rule_wired_in(self):
        config = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True, "mode": "log-only"}}})
        state_path = self.project_root / "var" / "run" / "waf-mode-state.json"
        state_path.parent.mkdir(parents=True)
        from datetime import timedelta
        state_path.write_text(
            '{"mode": "log-only", "since": "' + (self.clock.now() - timedelta(days=30)).isoformat() + '"}'
        )
        result = self._run(config)
        self.assertTrue(any(f.rule_id == "WAF-001" for f in result.findings))

    def test_config_path_and_timestamp_recorded(self):
        result = self._run(OmegaServConfig())
        self.assertEqual(result.config_path, "config/omega-serve.json")
        self.assertEqual(result.timestamp, self.clock.now())


if __name__ == "__main__":
    unittest.main()
