"""Teste BackupMetadataStore contre de vrais fichiers JSON temporaires."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.persistence.snapshots import SnapshotMetadata, SnapshotStatus
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore


class TestBackupMetadataStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = BackupMetadataStore(Path(self._tmp.name) / "backups")

    def tearDown(self):
        self._tmp.cleanup()

    def _metadata(self, snapshot_id: str = "snapshot_1", **overrides) -> SnapshotMetadata:
        defaults = {
            "snapshot_id": snapshot_id,
            "created_at": datetime(2026, 9, 8, 17, 0, 0, tzinfo=timezone.utc),
            "scope": "config",
            "description": "test",
        }
        defaults.update(overrides)
        return SnapshotMetadata(**defaults)

    def test_load_missing_returns_none(self):
        self.assertIsNone(self.store.load("does-not-exist"))

    def test_save_then_load_round_trips(self):
        metadata = self._metadata(file_path="/tmp/x.tar.gz", file_size_bytes=42)
        self.store.save(metadata)
        loaded = self.store.load("snapshot_1")
        self.assertEqual(loaded, metadata)

    def test_list_all_sorted_newest_first(self):
        self.store.save(self._metadata("snapshot_a", created_at=datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)))
        self.store.save(self._metadata("snapshot_b", created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)))
        all_metadata = self.store.list_all()
        self.assertEqual([m.snapshot_id for m in all_metadata], ["snapshot_b", "snapshot_a"])

    def test_delete_existing_returns_true_and_removes_file(self):
        self.store.save(self._metadata())
        self.assertTrue(self.store.delete("snapshot_1"))
        self.assertIsNone(self.store.load("snapshot_1"))

    def test_delete_missing_returns_false(self):
        self.assertFalse(self.store.delete("does-not-exist"))

    def test_round_trips_failed_status_with_error_message(self):
        metadata = self._metadata(status=SnapshotStatus.FAILED, error_message="boom")
        self.store.save(metadata)
        loaded = self.store.load("snapshot_1")
        self.assertEqual(loaded.status, SnapshotStatus.FAILED)
        self.assertEqual(loaded.error_message, "boom")


if __name__ == "__main__":
    unittest.main()
