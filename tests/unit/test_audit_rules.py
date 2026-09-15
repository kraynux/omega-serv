# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.audit.rules import (
    PURE_RULES,
    rule_csp_too_permissive,
    rule_csp_unsafe_inline,
    rule_dangerous_methods,
    rule_high_timeouts,
    rule_public_bind,
    rule_upload_zones_without_type_restriction,
)


class TestRulePublicBind(unittest.TestCase):
    def test_wildcard_bind_flagged(self):
        config = OmegaServConfig.from_dict({"server": {"bind": "0.0.0.0"}})
        findings = rule_public_bind(config)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "TLS-003")

    def test_ipv6_wildcard_bind_flagged(self):
        config = OmegaServConfig.from_dict({"server": {"bind": "::"}})
        self.assertEqual(len(rule_public_bind(config)), 1)

    def test_localhost_bind_not_flagged(self):
        config = OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1"}})
        self.assertEqual(rule_public_bind(config), [])


class TestRuleCspUnsafeInline(unittest.TestCase):
    def test_unsafe_inline_flagged(self):
        config = OmegaServConfig()
        findings = rule_csp_unsafe_inline(config, csp_policy="default-src 'unsafe-inline'")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "CSP-001")

    def test_strict_csp_not_flagged(self):
        config = OmegaServConfig()
        findings = rule_csp_unsafe_inline(config, csp_policy="default-src 'self'")
        self.assertEqual(findings, [])

    def test_default_real_policy_is_not_flagged(self):
        # La CSP reelle du projet (domain/security/csp.py) ne contient
        # deja pas unsafe-inline - regression si elle en acquiert un un jour.
        self.assertEqual(rule_csp_unsafe_inline(OmegaServConfig()), [])


class TestRuleCspTooPermissive(unittest.TestCase):
    def test_wildcard_source_flagged(self):
        findings = rule_csp_too_permissive(OmegaServConfig(), csp_policy="default-src *; script-src 'self'")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "CSP-002")
        self.assertIn("default-src", findings[0].details["directives"])

    def test_no_wildcard_not_flagged(self):
        findings = rule_csp_too_permissive(OmegaServConfig(), csp_policy="default-src 'self'; script-src 'self'")
        self.assertEqual(findings, [])

    def test_default_real_policy_is_not_flagged(self):
        self.assertEqual(rule_csp_too_permissive(OmegaServConfig()), [])


class TestRuleDangerousMethods(unittest.TestCase):
    def test_delete_method_flagged(self):
        config = OmegaServConfig.from_dict({"security": {"allowed_methods": ["GET", "HEAD", "DELETE"]}})
        findings = rule_dangerous_methods(config)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity.value, "high")

    def test_default_methods_not_flagged(self):
        self.assertEqual(rule_dangerous_methods(OmegaServConfig()), [])


class TestRuleHighTimeouts(unittest.TestCase):
    def test_high_read_timeout_flagged(self):
        config = OmegaServConfig.from_dict({"server": {"read_timeout_seconds": 120}})
        self.assertEqual(len(rule_high_timeouts(config)), 1)

    def test_default_timeout_not_flagged(self):
        self.assertEqual(rule_high_timeouts(OmegaServConfig()), [])


class TestRuleUploadZonesWithoutTypeRestriction(unittest.TestCase):
    def _config(self, **zone_overrides):
        zone = {"url_prefix": "/upload/", "storage_path": "var/uploads/public"}
        zone.update(zone_overrides)
        return OmegaServConfig.from_dict({"options": {"upload": {"enabled": True, "zones": [zone]}}})

    def test_zone_without_any_restriction_flagged(self):
        findings = rule_upload_zones_without_type_restriction(self._config())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "UPLOAD-001")

    def test_zone_with_allowed_extensions_not_flagged(self):
        config = self._config(policy={"allowed_extensions": [".jpg"]})
        self.assertEqual(rule_upload_zones_without_type_restriction(config), [])

    def test_zone_with_allowed_content_types_not_flagged(self):
        config = self._config(policy={"allowed_content_types": ["image/jpeg"]})
        self.assertEqual(rule_upload_zones_without_type_restriction(config), [])

    def test_disabled_upload_option_not_flagged(self):
        config = OmegaServConfig.from_dict({"options": {"upload": {
            "enabled": False,
            "zones": [{"url_prefix": "/upload/", "storage_path": "var/uploads"}],
        }}})
        self.assertEqual(rule_upload_zones_without_type_restriction(config), [])

    def test_no_upload_option_at_all_not_flagged(self):
        self.assertEqual(rule_upload_zones_without_type_restriction(OmegaServConfig()), [])

    def test_multiple_zones_each_evaluated_independently(self):
        config = OmegaServConfig.from_dict({"options": {"upload": {
            "enabled": True,
            "zones": [
                {"url_prefix": "/a/", "storage_path": "var/uploads/a", "policy": {"allowed_extensions": [".png"]}},
                {"url_prefix": "/b/", "storage_path": "var/uploads/b"},
            ],
        }}})
        findings = rule_upload_zones_without_type_restriction(config)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].details["url_prefix"], "/b/")


class TestPureRulesRegistry(unittest.TestCase):
    def test_all_pure_rules_are_callable_with_config_only(self):
        config = OmegaServConfig()
        for rule in PURE_RULES:
            findings = rule(config)
            self.assertIsInstance(findings, list)


if __name__ == "__main__":
    unittest.main()
