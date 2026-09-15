# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste restore_backup (application/persistence/restore_backup.py)
contre un vrai ArchiveStore/BackupMetadataStore."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.persistence.create_backup import create_backup
from omega_serv.application.persistence.restore_backup import restore_backup
from omega_serv.domain.config.entities import OmegaServConfig, PathsConfig
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.domain.persistence.snapshots import SnapshotStatus
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore


class _FixedClock:
    def now(self):
        return datetime(2026, 9, 8, 17, 0, 0, 123456, tzinfo=timezone.utc)


class TestRestoreBackup(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.archive_store = ArchiveStore(self.root / "var" / "backups" / "config-snapshots")
        self.metadata_store = BackupMetadataStore(self.root / "var" / "backups" / "config-snapshots")
        self.config_file = self.root / "config" / "omega-serve.json"
        self.config_file.parent.mkdir(parents=True)
        self.config_file.write_text('{"version": 1}')

    def tearDown(self):
        self._tmp.cleanup()

    def _make_backup(self) -> str:
        request = BackupRequest()
        result = create_backup(
            request, OmegaServConfig(paths=PathsConfig()), self.root, self.config_file,
            self.archive_store, self.metadata_store, _FixedClock(),
        )
        self.assertTrue(result.success)
        return result.metadata.snapshot_id

    def test_missing_snapshot_fails(self):
        result = restore_backup("does-not-exist", self.root, self.archive_store, self.metadata_store)
        self.assertFalse(result.success)

    def test_restores_and_overwrites_current_file(self):
        snapshot_id = self._make_backup()
        self.config_file.write_text("CORRUPTED")
        result = restore_backup(snapshot_id, self.root, self.archive_store, self.metadata_store)
        self.assertTrue(result.success)
        self.assertEqual(self.config_file.read_text(), '{"version": 1}')

    def test_restores_after_file_deleted(self):
        snapshot_id = self._make_backup()
        self.config_file.unlink()
        result = restore_backup(snapshot_id, self.root, self.archive_store, self.metadata_store)
        self.assertTrue(result.success)
        self.assertTrue(self.config_file.exists())

    def test_marks_metadata_restored_after_success(self):
        snapshot_id = self._make_backup()
        restore_backup(snapshot_id, self.root, self.archive_store, self.metadata_store)
        metadata = self.metadata_store.load(snapshot_id)
        self.assertEqual(metadata.status, SnapshotStatus.RESTORED)

    def test_marks_metadata_failed_when_archive_missing_on_disk(self):
        snapshot_id = self._make_backup()
        archive_path = self.archive_store.base_dir / f"{snapshot_id}.tar.gz"
        archive_path.unlink()
        result = restore_backup(snapshot_id, self.root, self.archive_store, self.metadata_store)
        self.assertFalse(result.success)
        metadata = self.metadata_store.load(snapshot_id)
        self.assertEqual(metadata.status, SnapshotStatus.FAILED)
        self.assertIsNotNone(metadata.error_message)


if __name__ == "__main__":
    unittest.main()
