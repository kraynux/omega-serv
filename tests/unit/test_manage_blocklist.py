# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.application.security.manage_blocklist import (
    add_blocklist_entry,
    remove_blocklist_entry,
)


class _FakeBlocklist:
    def __init__(self):
        self.entries = []

    def is_blocked(self, ip):
        return None

    def list_entries(self):
        return tuple(self.entries)

    def add_entry(self, entry):
        self.entries.append(entry)

    def remove_entry(self, network):
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.network != network]
        return len(self.entries) < before

    def purge_expired(self):
        return 0

    def count_auto_entries(self):
        return 0


class TestAddBlocklistEntry(unittest.TestCase):
    def test_temporary_ban_succeeds_without_confirmation(self):
        blocklist = _FakeBlocklist()
        result = add_blocklist_entry(blocklist, "203.0.113.1/32", "test", duration_seconds=3600)
        self.assertTrue(result.success)
        self.assertEqual(len(blocklist.entries), 1)
        self.assertIsNotNone(blocklist.entries[0].expires_at)

    def test_permanent_ban_refused_without_confirmation(self):
        blocklist = _FakeBlocklist()
        result = add_blocklist_entry(blocklist, "203.0.113.1/32", "test", duration_seconds=None)
        self.assertFalse(result.success)
        self.assertEqual(len(blocklist.entries), 0)

    def test_permanent_ban_succeeds_with_confirmation(self):
        blocklist = _FakeBlocklist()
        result = add_blocklist_entry(blocklist, "203.0.113.1/32", "test", duration_seconds=None, confirm_permanent=True)
        self.assertTrue(result.success)
        self.assertIsNone(blocklist.entries[0].expires_at)

    def test_invalid_network_rejected(self):
        blocklist = _FakeBlocklist()
        result = add_blocklist_entry(blocklist, "not-an-ip", "test", duration_seconds=3600)
        self.assertFalse(result.success)
        self.assertEqual(len(blocklist.entries), 0)


class TestRemoveBlocklistEntry(unittest.TestCase):
    def test_removes_existing_entry(self):
        blocklist = _FakeBlocklist()
        add_blocklist_entry(blocklist, "203.0.113.1/32", "test", duration_seconds=3600)
        result = remove_blocklist_entry(blocklist, "203.0.113.1/32")
        self.assertTrue(result.success)
        self.assertEqual(len(blocklist.entries), 0)

    def test_missing_entry_reports_failure(self):
        blocklist = _FakeBlocklist()
        result = remove_blocklist_entry(blocklist, "203.0.113.1/32")
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
