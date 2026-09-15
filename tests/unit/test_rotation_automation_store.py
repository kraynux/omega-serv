# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste RotationAutomationStore contre de vrais fichiers JSON temporaires."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.logging.rotation_automation_store import RotationAutomationStore


class TestRotationAutomationStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "run" / "automations.json"
        self.store = RotationAutomationStore(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_all_missing_file_returns_empty(self):
        self.assertEqual(self.store.list_all(), [])

    def test_add_then_list_all(self):
        self.store.add({"log_id": "access", "days_interval": 7})
        self.assertEqual(self.store.list_all(), [{"log_id": "access", "days_interval": 7}])

    def test_add_creates_parent_directory(self):
        self.store.add({"log_id": "access"})
        self.assertTrue(self.path.exists())

    def test_delete_valid_index_removes_entry(self):
        self.store.add({"log_id": "access"})
        self.store.add({"log_id": "error"})
        self.assertTrue(self.store.delete(0))
        self.assertEqual(self.store.list_all(), [{"log_id": "error"}])

    def test_delete_invalid_index_returns_false(self):
        self.store.add({"log_id": "access"})
        self.assertFalse(self.store.delete(5))
        self.assertEqual(len(self.store.list_all()), 1)

    def test_list_all_with_corrupted_json_returns_empty(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("not json", encoding="utf-8")
        self.assertEqual(self.store.list_all(), [])


if __name__ == "__main__":
    unittest.main()
