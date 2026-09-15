# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste create_backup (application/persistence/create_backup.py) contre
un vrai ArchiveStore/BackupMetadataStore et un vrai projet temporaire."""
from __future__ import annotations

import tarfile
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.persistence.create_backup import create_backup
from omega_serv.domain.config.entities import OmegaServConfig, PathsConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore


class _FixedClock:
    def now(self):
        return datetime(2026, 9, 8, 17, 0, 0, 123456, tzinfo=timezone.utc)


class TestCreateBackup(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.archive_store = ArchiveStore(self.root / "var" / "backups" / "config-snapshots")
        self.metadata_store = BackupMetadataStore(self.root / "var" / "backups" / "config-snapshots")
        self.clock = _FixedClock()
        self.config_file = self.root / "config" / "omega-serve.json"
        self.config_file.parent.mkdir(parents=True)
        self.config_file.write_text('{"version": 1}')

    def tearDown(self):
        self._tmp.cleanup()

    def _config(self, **options) -> OmegaServConfig:
        return OmegaServConfig(paths=PathsConfig(), options=options)

    def test_no_components_selected_fails(self):
        request = BackupRequest(include_config=False)
        result = create_backup(request, self._config(), self.root, self.config_file, self.archive_store, self.metadata_store, self.clock)
        self.assertFalse(result.success)

    def test_config_only_creates_archive_and_metadata(self):
        request = BackupRequest()
        result = create_backup(request, self._config(), self.root, self.config_file, self.archive_store, self.metadata_store, self.clock)
        self.assertTrue(result.success)
        self.assertEqual(result.metadata.scope, "config")
        self.assertTrue(Path(result.metadata.file_path).exists())
        with tarfile.open(result.metadata.file_path) as tar:
            self.assertIn("config/omega-serve.json", tar.getnames())

    def test_config_file_outside_project_root_is_archived_by_bare_name(self):
        outside_dir = Path(tempfile.mkdtemp())
        try:
            outside_config = outside_dir / "custom.json"
            outside_config.write_text('{"version": 1}')
            request = BackupRequest()
            result = create_backup(
                request, self._config(), self.root, outside_config, self.archive_store, self.metadata_store, self.clock
            )
            self.assertTrue(result.success)
            with tarfile.open(result.metadata.file_path) as tar:
                self.assertIn("custom.json", tar.getnames())
        finally:
            import shutil

            shutil.rmtree(outside_dir)

    def test_include_auth_zones_archives_auth_files(self):
        (self.root / "secure" / "auth").mkdir(parents=True)
        (self.root / "secure" / "auth" / "users.json").write_text("[]")
        (self.root / "secure" / "auth" / "zones.json").write_text("[]")
        request = BackupRequest(include_auth_zones=True)
        result = create_backup(request, self._config(), self.root, self.config_file, self.archive_store, self.metadata_store, self.clock)
        self.assertTrue(result.success)
        self.assertEqual(result.metadata.scope, "config+auth")
        with tarfile.open(result.metadata.file_path) as tar:
            names = tar.getnames()
            self.assertIn("secure/auth/users.json", names)
            self.assertIn("secure/auth/zones.json", names)

    def test_include_certificates_archives_whole_directory_recursively(self):
        cert_dir = self.root / "secure" / "certificates" / "server"
        cert_dir.mkdir(parents=True)
        (cert_dir / "server.pem").write_text("CERT")
        (cert_dir / "server.key").write_text("KEY")
        request = BackupRequest(include_certificates=True)
        result = create_backup(request, self._config(), self.root, self.config_file, self.archive_store, self.metadata_store, self.clock)
        self.assertTrue(result.success)
        with tarfile.open(result.metadata.file_path) as tar:
            names = tar.getnames()
            self.assertIn("secure/certificates/server/server.pem", names)
            self.assertIn("secure/certificates/server/server.key", names)

    def test_include_waf_rules_archives_rule_paths_and_blocklist(self):
        (self.root / "secure" / "waf" / "rules").mkdir(parents=True)
        (self.root / "secure" / "waf" / "rules" / "sqli.json").write_text("[]")
        (self.root / "secure" / "waf" / "blocklist.json").write_text("[]")
        waf_option = Option(
            name="waf", enabled=True,
            settings={"rules": {"paths": ["secure/waf/rules/sqli.json"]}, "blocklist": {"path": "secure/waf/blocklist.json"}},
        )
        request = BackupRequest(include_waf_rules=True)
        result = create_backup(
            request, self._config(waf=waf_option), self.root, self.config_file, self.archive_store, self.metadata_store, self.clock
        )
        self.assertTrue(result.success)
        with tarfile.open(result.metadata.file_path) as tar:
            names = tar.getnames()
            self.assertIn("secure/waf/rules/sqli.json", names)
            self.assertIn("secure/waf/blocklist.json", names)

    def test_missing_sources_are_skipped_not_fatal(self):
        request = BackupRequest(include_certificates=True)
        result = create_backup(request, self._config(), self.root, self.config_file, self.archive_store, self.metadata_store, self.clock)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
