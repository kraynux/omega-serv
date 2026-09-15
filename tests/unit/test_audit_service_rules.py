# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.security.service_rules import check_log_sizes, check_service_unit


class TestCheckServiceUnit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_unit_file_not_flagged(self):
        unit_path = self.root / "omega-serv.service"
        self.assertEqual(check_service_unit(unit_path, self.filesystem), [])

    def test_unit_with_user_and_group_not_flagged(self):
        unit_path = self.root / "omega-serv.service"
        unit_path.write_text("[Service]\nUser=omega-serv\nGroup=omega-serv\n")
        self.assertEqual(check_service_unit(unit_path, self.filesystem), [])

    def test_unit_without_user_flagged_as_svc_001(self):
        unit_path = self.root / "omega-serv.service"
        unit_path.write_text("[Service]\nExecStart=/usr/bin/omega-serv serve\n")
        findings = check_service_unit(unit_path, self.filesystem)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "SVC-001")

    def test_unit_with_user_but_no_group_flagged(self):
        unit_path = self.root / "omega-serv.service"
        unit_path.write_text("[Service]\nUser=omega-serv\n")
        findings = check_service_unit(unit_path, self.filesystem)
        self.assertEqual(len(findings), 1)


class TestCheckLogSizes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        (self.project_root / "var" / "log").mkdir(parents=True)
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_rotation_disabled_flagged(self):
        config = OmegaServConfig.from_dict({"logs": {"rotation": {"enabled": False}}})
        findings = check_log_sizes(config, self.project_root, self.filesystem)
        self.assertTrue(any("Rotation" in f.rule_name for f in findings))

    def test_rotation_enabled_and_small_logs_no_findings(self):
        (self.project_root / "var" / "log" / "access.log").write_text("small")
        config = OmegaServConfig()
        findings = check_log_sizes(config, self.project_root, self.filesystem)
        self.assertEqual(findings, [])

    def test_oversized_log_flagged(self):
        big_log = self.project_root / "var" / "log" / "access.log"
        with open(big_log, "wb") as f:
            f.seek(101 * 1024 * 1024 - 1)
            f.write(b"\0")
        config = OmegaServConfig()
        findings = check_log_sizes(config, self.project_root, self.filesystem)
        self.assertTrue(any(f.rule_id == "SVC-002" and "access" in f.rule_name for f in findings))

    def test_missing_log_file_not_flagged(self):
        config = OmegaServConfig()
        findings = check_log_sizes(config, self.project_root, self.filesystem)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
