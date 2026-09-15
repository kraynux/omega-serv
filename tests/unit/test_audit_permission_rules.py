# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.security.permission_rules import check_permissions


class TestCheckPermissions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "webroot").mkdir()
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_findings_on_fresh_project(self):
        config = OmegaServConfig()
        self.assertEqual(check_permissions(config, self.project_root, self.filesystem), [])

    def test_auth_disabled_skips_permission_check_even_if_file_is_world_readable(self):
        auth_file = self.project_root / "secure" / "auth" / "users.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("{}")
        auth_file.chmod(0o644)
        config = OmegaServConfig.from_dict({"options": {"auth": {"enabled": False}}})
        self.assertEqual(check_permissions(config, self.project_root, self.filesystem), [])

    def test_world_readable_auth_file_flagged_as_perm_002(self):
        auth_file = self.project_root / "secure" / "auth" / "users.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("{}")
        auth_file.chmod(0o644)
        config = OmegaServConfig.from_dict({"options": {"auth": {"enabled": True}}})
        findings = check_permissions(config, self.project_root, self.filesystem)
        self.assertTrue(any(f.rule_id == "PERM-002" for f in findings))

    def test_auth_file_restricted_to_owner_not_flagged(self):
        auth_file = self.project_root / "secure" / "auth" / "users.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("{}")
        auth_file.chmod(0o600)
        config = OmegaServConfig.from_dict({"options": {"auth": {"enabled": True}}})
        findings = check_permissions(config, self.project_root, self.filesystem)
        self.assertEqual([f for f in findings if f.rule_id == "PERM-002"], [])

    def test_missing_auth_file_not_flagged(self):
        config = OmegaServConfig.from_dict({"options": {"auth": {"enabled": True}}})
        findings = check_permissions(config, self.project_root, self.filesystem)
        self.assertEqual([f for f in findings if f.rule_id == "PERM-002"], [])

    def test_env_file_under_webroot_flagged_as_perm_003(self):
        (self.project_root / "webroot" / ".env").write_text("SECRET=1")
        config = OmegaServConfig()
        findings = check_permissions(config, self.project_root, self.filesystem)
        self.assertTrue(any(f.rule_id == "PERM-003" for f in findings))

    def test_sensitive_file_in_nested_directory_still_detected(self):
        nested = self.project_root / "webroot" / "sub" / "dir"
        nested.mkdir(parents=True)
        (nested / "id_rsa.key").write_text("private")
        config = OmegaServConfig()
        findings = check_permissions(config, self.project_root, self.filesystem)
        self.assertTrue(any(f.rule_id == "PERM-003" for f in findings))

    def test_ordinary_file_under_webroot_not_flagged(self):
        (self.project_root / "webroot" / "index.html").write_text("<html></html>")
        config = OmegaServConfig()
        findings = check_permissions(config, self.project_root, self.filesystem)
        self.assertEqual([f for f in findings if f.rule_id == "PERM-003"], [])


if __name__ == "__main__":
    unittest.main()
