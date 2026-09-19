import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.config.load_config import load_config
from omega_serv.application.config.validate_config import validate_config_environment
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.config.json_config_repository import JsonConfigRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config_path = self.root / "omega-serve.json"
        self.filesystem = LocalFilesystem()
        self.repo = JsonConfigRepository(self.filesystem, backups_dir=self.root / "backups")

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_valid_config_succeeds(self):
        self.repo.save(self.config_path, OmegaServConfig())
        result = load_config(self.repo, self.config_path)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.config)
        self.assertEqual(result.errors, [])

    def test_load_missing_file_fails_with_error(self):
        result = load_config(self.repo, self.config_path / "does-not-exist.json")
        self.assertFalse(result.success)
        self.assertTrue(result.errors)

    def test_load_structurally_invalid_config_fails(self):
        bad_config = OmegaServConfig.from_dict({"server": {"port": 999999}})
        self.repo.save(self.config_path, bad_config)
        result = load_config(self.repo, self.config_path)
        self.assertFalse(result.success)
        self.assertTrue(any("port" in e for e in result.errors))


class TestValidateConfigEnvironment(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "webroot").mkdir()
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_existing_webroot_passes(self):
        config = OmegaServConfig()
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_missing_webroot_fails(self):
        config = OmegaServConfig.from_dict({"paths": {"webroot": "does-not-exist"}})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("webroot" in e for e in errors))

    def test_secure_inside_webroot_is_rejected(self):
        config = OmegaServConfig.from_dict({"paths": {"secure": "webroot/secure"}})
        (self.project_root / "webroot" / "secure").mkdir()
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("paths.secure" in e for e in errors))

    def test_waf_disabled_skips_waf_checks_even_with_no_rule_paths(self):
        config = OmegaServConfig.from_dict({"options": {"waf": {"enabled": False}}})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_waf_enabled_with_empty_rule_paths_fails(self):
        config = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True}}})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("rules.paths" in e for e in errors))

    def test_waf_enabled_with_missing_rule_file_fails(self):
        config = OmegaServConfig.from_dict({
            "options": {"waf": {"enabled": True, "rules": {"paths": ["secure/waf/rules/missing.json"]}}},
        })
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("rules.paths" in e for e in errors))

    def test_waf_enabled_with_valid_rule_file_passes(self):
        rules_dir = self.project_root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "core.json").write_text(
            '{"version": 1, "pack": "core", "enabled": true, "rules": []}'
        )
        config = OmegaServConfig.from_dict({
            "options": {"waf": {"enabled": True, "rules": {"paths": ["secure/waf/rules/core.json"]}}},
        })
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])


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


class TestValidateTlsEnvironment(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "webroot").mkdir()
        self.cert_dir = self.project_root / "secure" / "certificates" / "server"
        self.cert_dir.mkdir(parents=True)
        self.key_path = self.cert_dir / "server.key"
        self.cert_path = self.cert_dir / "server.pem"
        self.key_path.write_text("key")
        self.key_path.chmod(0o600)
        self.cert_path.write_text("cert")
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _cert(self, not_after=None):
        from omega_serv.domain.security.tls.entities import CertificateInfo
        now = datetime.now(timezone.utc)
        return CertificateInfo(subject="CN=localhost", issuer="CN=localhost", not_before=now - timedelta(days=1), not_after=not_after or (now + timedelta(days=100)))

    def _config(self, **overrides):
        data = {
            "tls": {
                "enabled": True, "mode": "direct",
                "certificate": {
                    "certificate_path": "secure/certificates/server/server.pem",
                    "private_key_path": "secure/certificates/server/server.key",
                },
            },
        }
        data.update(overrides)
        return OmegaServConfig.from_dict(data)

    def test_tls_disabled_skips_certificate_checks_even_without_files(self):
        config = OmegaServConfig.from_dict({"tls": {"enabled": False}})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_healthy_certificate_passes(self):
        config = self._config()
        errors = validate_config_environment(config, self.filesystem, self.project_root, _FakeCertificateTool(self._cert()))
        self.assertEqual(errors, [])

    def test_missing_certificate_file_fails(self):
        self.cert_path.unlink()
        config = self._config()
        errors = validate_config_environment(config, self.filesystem, self.project_root, _FakeCertificateTool(self._cert()))
        self.assertTrue(any("certificate_path introuvable" in e for e in errors))

    def test_world_readable_key_fails(self):
        self.key_path.chmod(0o644)
        config = self._config()
        errors = validate_config_environment(config, self.filesystem, self.project_root, _FakeCertificateTool(self._cert()))
        self.assertTrue(any("cle privee" in e for e in errors))

    def test_expired_certificate_fails(self):
        expired = self._cert(not_after=datetime.now(timezone.utc) - timedelta(days=1))
        config = self._config()
        errors = validate_config_environment(config, self.filesystem, self.project_root, _FakeCertificateTool(expired))
        self.assertTrue(any("expire" in e for e in errors))

    def test_key_cert_mismatch_fails(self):
        config = self._config()
        errors = validate_config_environment(config, self.filesystem, self.project_root, _FakeCertificateTool(self._cert(), keys_match=False))
        self.assertTrue(any("correspond" in e for e in errors))

    def test_self_signed_public_bind_without_confirmation_fails(self):
        config = self._config(server={"bind": "0.0.0.0"})
        errors = validate_config_environment(config, self.filesystem, self.project_root, _FakeCertificateTool(self._cert()))
        self.assertTrue(any("auto-signe" in e for e in errors))

    def test_self_signed_public_bind_with_confirmation_passes(self):
        config = self._config(server={"bind": "0.0.0.0"})
        errors = validate_config_environment(
            config, self.filesystem, self.project_root, _FakeCertificateTool(self._cert()),
            self_signed_public_bind_confirmed=True,
        )
        self.assertEqual(errors, [])

    def test_certificate_inside_webroot_rejected(self):
        cert_in_webroot = self.project_root / "webroot" / "server.pem"
        cert_in_webroot.write_text("cert")
        config = self._config(tls={
            "enabled": True, "mode": "direct",
            "certificate": {"certificate_path": "webroot/server.pem", "private_key_path": "secure/certificates/server/server.key"},
        })
        errors = validate_config_environment(config, self.filesystem, self.project_root, _FakeCertificateTool(self._cert()))
        self.assertTrue(any("webroot" in e for e in errors))


class TestValidateAuthEnvironment(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "webroot").mkdir()
        (self.project_root / "secure" / "auth").mkdir(parents=True)
        self.zones_path = self.project_root / "secure" / "auth" / "zones.json"
        self.users_path = self.project_root / "secure" / "auth" / "users.json"
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _config(self, **overrides):
        data = {"options": {"auth": {"enabled": True}}, "server": {"bind": "127.0.0.1"}}
        data.update(overrides)
        return OmegaServConfig.from_dict(data)

    def test_auth_disabled_skips_checks(self):
        self.zones_path.write_text('{ not json')
        config = OmegaServConfig.from_dict({"options": {"auth": {"enabled": False}}})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_no_zones_file_passes(self):
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_valid_zone_with_known_user_passes(self):
        self.zones_path.write_text(
            '{"version": 1, "zones": [{"path_prefix": "/private/", "realm": "Zone", "allowed_users": ["admin"]}]}'
        )
        self.users_path.write_text('{"version": 1, "users": [{"username": "admin", "password_hash": "x"}]}')
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_invalid_zone_structure_fails(self):
        self.zones_path.write_text(
            '{"version": 1, "zones": [{"path_prefix": "no-leading-slash", "realm": "Zone", "allowed_users": ["admin"]}]}'
        )
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertTrue(errors)

    def test_zone_referencing_unknown_user_fails(self):
        self.zones_path.write_text(
            '{"version": 1, "zones": [{"path_prefix": "/private/", "realm": "Zone", "allowed_users": ["ghost"]}]}'
        )
        self.users_path.write_text('{"version": 1, "users": [{"username": "admin", "password_hash": "x"}]}')
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertTrue(any("ghost" in e for e in errors))

    def test_malformed_zones_file_fails(self):
        self.zones_path.write_text("{ not json")
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertTrue(errors)

    def test_auth_without_tls_on_public_bind_fails(self):
        config = self._config(server={"bind": "0.0.0.0"}, tls={"mode": "direct"})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("clair" in e for e in errors))

    def test_auth_without_tls_on_public_bind_passes_with_confirmation(self):
        config = self._config(server={"bind": "0.0.0.0"}, tls={"mode": "direct"})
        errors = validate_config_environment(config, self.filesystem, self.project_root, auth_without_tls_confirmed=True)
        self.assertEqual(errors, [])

    def test_auth_without_tls_on_local_bind_never_requires_confirmation(self):
        config = self._config(server={"bind": "127.0.0.1"}, tls={"mode": "direct"})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_auth_with_behind_proxy_tls_mode_never_requires_confirmation(self):
        config = self._config(server={"bind": "0.0.0.0"}, tls={"enabled": False, "mode": "behind_proxy"})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])


class TestValidateFastCgiEnvironment(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "webroot").mkdir()
        self.script_root = self.project_root / "php-app"
        self.script_root.mkdir()
        self.socket_path = self.project_root / "var" / "run" / "php-fpm.sock"
        self.socket_path.parent.mkdir(parents=True)
        self.socket_path.write_text("")  # existence suffit pour ce validateur, pas un vrai socket
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _config(self, **fastcgi_overrides):
        settings = {
            "enabled": True, "url_prefix": "/app/", "script_root": "php-app",
            "socket_path": "var/run/php-fpm.sock",
        }
        settings.update(fastcgi_overrides)
        return OmegaServConfig.from_dict({"options": {"fastcgi": settings}})

    def test_disabled_skips_checks(self):
        config = OmegaServConfig.from_dict({"options": {"fastcgi": {"enabled": False}}})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_valid_config_passes(self):
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_script_root_inside_webroot_rejected(self):
        (self.project_root / "webroot" / "php-app").mkdir()
        config = self._config(script_root="webroot/php-app")
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("webroot" in e for e in errors))

    def test_missing_script_root_directory_rejected(self):
        config = self._config(script_root="does-not-exist")
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("script_root" in e for e in errors))

    def test_missing_socket_rejected(self):
        config = self._config(socket_path="var/run/does-not-exist.sock")
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("socket_path" in e for e in errors))

    def test_empty_url_prefix_rejected(self):
        config = self._config(url_prefix="no-leading-slash")
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("url_prefix" in e for e in errors))


class TestValidateUploadEnvironment(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "webroot").mkdir()
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _config(self, storage_path="var/uploads/public"):
        return OmegaServConfig.from_dict({"options": {"upload": {
            "enabled": True,
            "zones": [{"url_prefix": "/upload/", "storage_path": storage_path, "policy": {}}],
        }}})

    def test_disabled_skips_checks(self):
        config = OmegaServConfig.from_dict({"options": {"upload": {"enabled": False}}})
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_valid_config_passes_even_when_storage_dir_does_not_exist_yet(self):
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertEqual(errors, [])

    def test_storage_path_colliding_with_existing_file_rejected(self):
        (self.project_root / "var").mkdir()
        (self.project_root / "var" / "uploads").write_text("i am a file, not a directory")
        config = self._config(storage_path="var/uploads")
        errors = validate_config_environment(config, self.filesystem, self.project_root)
        self.assertTrue(any("storage_path" in e for e in errors))

    def test_storage_path_already_a_directory_passes(self):
        (self.project_root / "var" / "uploads" / "public").mkdir(parents=True)
        errors = validate_config_environment(self._config(), self.filesystem, self.project_root)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
