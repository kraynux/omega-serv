# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste les fonctions pures de domain/persistence/snapshots.py."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from omega_serv.domain.persistence.snapshots import (
    SnapshotMetadata,
    SnapshotStatus,
    create_snapshot_id,
)


class TestCreateSnapshotId(unittest.TestCase):
    def test_formats_id_with_microseconds(self):
        ts = datetime(2026, 9, 8, 17, 0, 3, 762484, tzinfo=timezone.utc)
        self.assertEqual(create_snapshot_id(ts), "snapshot_20260908_170003_762484")

    def test_two_calls_in_same_second_produce_different_ids(self):
        ts1 = datetime(2026, 9, 8, 17, 0, 3, 762484, tzinfo=timezone.utc)
        ts2 = datetime(2026, 9, 8, 17, 0, 3, 768628, tzinfo=timezone.utc)
        self.assertNotEqual(create_snapshot_id(ts1), create_snapshot_id(ts2))


class TestSnapshotMetadata(unittest.TestCase):
    def test_defaults(self):
        metadata = SnapshotMetadata(
            snapshot_id="snapshot_1", created_at=datetime(2026, 9, 8, tzinfo=timezone.utc), scope="config",
        )
        self.assertEqual(metadata.status, SnapshotStatus.COMPLETED)
        self.assertEqual(metadata.source_system, "omega-serv")
        self.assertIsNone(metadata.file_path)
        self.assertIsNone(metadata.error_message)


if __name__ == "__main__":
    unittest.main()
