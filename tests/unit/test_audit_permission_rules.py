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

    # 2026-11-15 (decision de l'auteur) : nommer chaque fichier, la raison et le contenu reel ; vide = information.
    def _sensitive(self):
        return {f.rule_id: f for f in check_permissions(OmegaServConfig(), self.project_root, self.filesystem)
                if f.rule_id in ("PERM-003", "PERM-004")}

    def test_findings_name_each_file_with_reason_and_real_content(self):
        icons = self.project_root / "webroot" / "icons"
        icons.mkdir()
        (icons / "exemple.pem").write_text("")
        (icons / "exemple.key").write_text("  \n")
        (self.project_root / "webroot" / "server.key").write_text(
            "-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----\n")
        (self.project_root / "webroot" / ".env").write_text("SECRET=1")
        found = self._sensitive()
        self.assertEqual(found["PERM-003"].severity.value, "critical")
        self.assertEqual(found["PERM-004"].severity.value, "info")
        real = {e["path"]: e for e in found["PERM-003"].details["entries"]}
        self.assertEqual(real["server.key"]["content"], "private_key")
        self.assertEqual(real[".env"]["content"], "content")
        self.assertIn(".env", real[".env"]["reason"])
        self.assertIn(".key", real["server.key"]["reason"])
        empty = {e["path"] for e in found["PERM-004"].details["entries"]}
        self.assertEqual(empty, {"icons/exemple.pem", "icons/exemple.key"})
        self.assertTrue(any("server.key" in line for line in found["PERM-003"].detail_lines))
        self.assertTrue(found["PERM-004"].message.startswith("2 "))

    def test_only_empty_files_give_no_critical_finding(self):
        (self.project_root / "webroot" / "a.pem").write_text("")
        found = self._sensitive()
        self.assertNotIn("PERM-003", found)
        self.assertIn("PERM-004", found)

    def test_git_directory_is_reported_itself(self):
        git = self.project_root / "webroot" / ".git"
        git.mkdir()
        (git / "HEAD").write_text("ref: refs/heads/main")
        entries = self._sensitive()["PERM-003"].details["entries"]
        self.assertEqual([(e["path"], e["content"]) for e in entries], [(".git", "directory")])

    def test_more_than_ten_files_are_summarised_on_screen_but_all_in_details(self):
        for index in range(13):
            (self.project_root / "webroot" / f"k{index:02}.key").write_text("x")
        finding = self._sensitive()["PERM-003"]
        self.assertEqual(len(finding.details["entries"]), 13)
        self.assertEqual(len(finding.detail_lines), 11)
        self.assertIn("3", finding.detail_lines[-1])


if __name__ == "__main__":
    unittest.main()
