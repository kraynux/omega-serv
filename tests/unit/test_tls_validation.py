import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.domain.security.tls.entities import CertificateInfo, SelfSignedCertParams
from omega_serv.domain.security.tls.validation import (
    CertificateImportFacts,
    TlsStartupFacts,
    validate_certificate_import,
    validate_self_signed_params,
    validate_tls_config_structure,
    validate_tls_startup,
)

_NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def _cert(subject="CN=localhost", issuer="CN=localhost", not_after=None):
    return CertificateInfo(subject=subject, issuer=issuer, not_before=_NOW - timedelta(days=1), not_after=not_after or (_NOW + timedelta(days=365)))


def _facts(**overrides):
    defaults = {
        "tls_enabled": True, "tls_mode": "direct", "bind_host": "127.0.0.1",
        "private_key_mode": 0o600, "certificate_info": _cert(), "keys_match": True,
        "hsts_enabled": False, "self_signed_public_bind_confirmed": False, "now": _NOW,
    }
    defaults.update(overrides)
    return TlsStartupFacts(**defaults)


class TestValidateSelfSignedParams(unittest.TestCase):
    def test_valid_params_pass(self):
        params = SelfSignedCertParams(common_name="localhost", san_dns=("localhost",))
        self.assertEqual(validate_self_signed_params(params), [])

    def test_empty_cn_rejected(self):
        params = SelfSignedCertParams(common_name="", san_dns=("localhost",))
        self.assertTrue(any("common_name" in e for e in validate_self_signed_params(params)))

    def test_no_san_rejected(self):
        params = SelfSignedCertParams(common_name="localhost")
        self.assertTrue(any("SAN" in e for e in validate_self_signed_params(params)))

    def test_san_ip_alone_is_sufficient(self):
        params = SelfSignedCertParams(common_name="localhost", san_ip=("127.0.0.1",))
        self.assertEqual(validate_self_signed_params(params), [])

    def test_invalid_key_type_rejected(self):
        params = SelfSignedCertParams(common_name="localhost", san_dns=("localhost",), key_type="dsa1024")  # type: ignore[arg-type]
        self.assertTrue(any("key_type" in e for e in validate_self_signed_params(params)))

    def test_zero_validity_days_rejected(self):
        params = SelfSignedCertParams(common_name="localhost", san_dns=("localhost",), validity_days=0)
        self.assertTrue(any("validity_days" in e for e in validate_self_signed_params(params)))


class TestValidateTlsConfigStructure(unittest.TestCase):
    def test_valid_direct_config_passes(self):
        errors = validate_tls_config_structure(True, "direct", "TLS1.2", "TLS1.3", "server.pem", "server.key")
        self.assertEqual(errors, [])

    def test_disabled_config_never_requires_paths(self):
        errors = validate_tls_config_structure(False, "direct", "TLS1.2", "TLS1.3", "", "")
        self.assertEqual(errors, [])

    def test_behind_proxy_never_requires_paths(self):
        errors = validate_tls_config_structure(True, "behind_proxy", "TLS1.2", "TLS1.3", "", "")
        self.assertEqual(errors, [])

    def test_invalid_mode_rejected(self):
        errors = validate_tls_config_structure(False, "hybrid", "TLS1.2", "TLS1.3", "", "")
        self.assertTrue(any("mode" in e for e in errors))

    def test_min_version_above_max_rejected(self):
        errors = validate_tls_config_structure(False, "direct", "TLS1.3", "TLS1.2", "", "")
        self.assertTrue(any("min_version" in e for e in errors))

    def test_enabled_direct_without_cert_path_rejected(self):
        errors = validate_tls_config_structure(True, "direct", "TLS1.2", "TLS1.3", "", "server.key")
        self.assertTrue(any("certificate_path" in e for e in errors))

    def test_enabled_direct_without_key_path_rejected(self):
        errors = validate_tls_config_structure(True, "direct", "TLS1.2", "TLS1.3", "server.pem", "")
        self.assertTrue(any("private_key_path" in e for e in errors))


class TestValidateTlsStartup(unittest.TestCase):
    def test_healthy_direct_config_passes(self):
        self.assertEqual(validate_tls_startup(_facts()), [])

    def test_hsts_without_tls_rejected(self):
        errors = validate_tls_startup(_facts(tls_enabled=False, hsts_enabled=True, certificate_info=None, keys_match=None, private_key_mode=None))
        self.assertTrue(any("hsts" in e.lower() for e in errors))

    def test_behind_proxy_mode_skips_certificate_gates(self):
        errors = validate_tls_startup(_facts(tls_mode="behind_proxy", certificate_info=None, keys_match=None, private_key_mode=None))
        self.assertEqual(errors, [])

    def test_world_readable_private_key_rejected(self):
        errors = validate_tls_startup(_facts(private_key_mode=0o644))
        self.assertTrue(any("cle privee" in e for e in errors))

    def test_group_readable_private_key_rejected(self):
        errors = validate_tls_startup(_facts(private_key_mode=0o640))
        self.assertTrue(any("cle privee" in e for e in errors))

    def test_strict_private_key_mode_passes(self):
        errors = validate_tls_startup(_facts(private_key_mode=0o600))
        self.assertEqual(errors, [])

    def test_expired_certificate_rejected(self):
        expired = _cert(not_after=_NOW - timedelta(days=1))
        errors = validate_tls_startup(_facts(certificate_info=expired))
        self.assertTrue(any("expire" in e for e in errors))

    def test_self_signed_public_bind_without_confirmation_rejected(self):
        errors = validate_tls_startup(_facts(bind_host="0.0.0.0", self_signed_public_bind_confirmed=False))
        self.assertTrue(any("auto-signe" in e for e in errors))

    def test_self_signed_public_bind_with_confirmation_passes(self):
        errors = validate_tls_startup(_facts(bind_host="0.0.0.0", self_signed_public_bind_confirmed=True))
        self.assertEqual(errors, [])

    def test_self_signed_local_bind_never_requires_confirmation(self):
        errors = validate_tls_startup(_facts(bind_host="127.0.0.1", self_signed_public_bind_confirmed=False))
        self.assertEqual(errors, [])

    def test_ca_signed_public_bind_never_requires_confirmation(self):
        ca_signed = _cert(issuer="CN=Real CA")
        errors = validate_tls_startup(_facts(bind_host="0.0.0.0", certificate_info=ca_signed, self_signed_public_bind_confirmed=False))
        self.assertEqual(errors, [])

    def test_keys_mismatch_rejected(self):
        errors = validate_tls_startup(_facts(keys_match=False))
        self.assertTrue(any("correspond" in e for e in errors))

    def test_keys_match_none_is_not_an_error(self):
        errors = validate_tls_startup(_facts(keys_match=None))
        self.assertEqual(errors, [])


def _import_facts(**overrides):
    defaults = {
        "source_key_exists": True, "source_cert_exists": True,
        "source_chain_path_given": False, "source_chain_exists": False,
        "keys_match": True, "certificate_info": _cert(), "now": _NOW,
    }
    defaults.update(overrides)
    return CertificateImportFacts(**defaults)


class TestValidateCertificateImport(unittest.TestCase):
    def test_healthy_import_passes(self):
        self.assertEqual(validate_certificate_import(_import_facts()), [])

    def test_missing_source_key_rejected(self):
        errors = validate_certificate_import(_import_facts(source_key_exists=False, keys_match=None))
        self.assertTrue(any("cle privee source" in e for e in errors))

    def test_missing_source_cert_rejected(self):
        errors = validate_certificate_import(
            _import_facts(source_cert_exists=False, keys_match=None, certificate_info=None)
        )
        self.assertTrue(any("certificat source" in e for e in errors))

    def test_declared_chain_missing_on_disk_rejected(self):
        errors = validate_certificate_import(
            _import_facts(source_chain_path_given=True, source_chain_exists=False)
        )
        self.assertTrue(any("chaine intermediaire" in e for e in errors))

    def test_declared_chain_present_on_disk_passes(self):
        errors = validate_certificate_import(
            _import_facts(source_chain_path_given=True, source_chain_exists=True)
        )
        self.assertEqual(errors, [])

    def test_mismatched_keys_rejected(self):
        errors = validate_certificate_import(_import_facts(keys_match=False))
        self.assertTrue(any("ne correspondent pas" in e for e in errors))

    def test_expired_certificate_rejected(self):
        expired = _cert(not_after=_NOW - timedelta(days=1))
        errors = validate_certificate_import(_import_facts(certificate_info=expired))
        self.assertTrue(any("expire" in e for e in errors))

if __name__ == "__main__":
    unittest.main()
