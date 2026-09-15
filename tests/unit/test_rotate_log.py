# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste le cas d'usage rotate_log_if_needed (application/logs/rotate_log.py)
contre un vrai LocalFilesystem et un vrai ArchiveStore."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.logs.rotate_log import rotate_log_if_needed
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore

_NOW = datetime(2026, 9, 8, 16, 27, 40, tzinfo=timezone.utc)


class TestRotateLogIfNeeded(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.archive_store = ArchiveStore(self.root / "archives")
        self.log_path = self.root / "access.log"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_log_reports_failure(self):
        result = rotate_log_if_needed(self.log_path, 1000, 3, self.filesystem, self.archive_store, now=_NOW)
        self.assertFalse(result.success)
        self.assertIn("introuvable", result.message)

    def test_below_threshold_does_not_rotate(self):
        self.log_path.write_text("small")
        result = rotate_log_if_needed(self.log_path, 1000, 3, self.filesystem, self.archive_store, now=_NOW)
        self.assertFalse(result.success)
        self.assertEqual(self.log_path.read_text(), "small")

    def test_above_threshold_archives_and_truncates(self):
        self.log_path.write_text("x" * 20)
        result = rotate_log_if_needed(self.log_path, 10, 3, self.filesystem, self.archive_store, now=_NOW)
        self.assertTrue(result.success)
        self.assertEqual(self.log_path.read_text(), "")
        archive = self.root / "archives" / "access.log.20260908-162740.tar.gz"
        self.assertTrue(archive.exists())

    def test_old_rotations_beyond_keep_are_deleted(self):
        for name in ("access.log.a.tar.gz", "access.log.b.tar.gz"):
            (self.root / "archives").mkdir(parents=True, exist_ok=True)
            (self.root / "archives" / name).write_bytes(b"fake")
        self.log_path.write_text("x" * 20)
        result = rotate_log_if_needed(self.log_path, 10, 2, self.filesystem, self.archive_store, now=_NOW)
        self.assertTrue(result.success)
        self.assertIn("supprimee", result.message)
        remaining = sorted(p.name for p in (self.root / "archives").glob("*.tar.gz"))
        self.assertEqual(len(remaining), 2)


if __name__ == "__main__":
    unittest.main()
