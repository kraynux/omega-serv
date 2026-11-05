"""Base RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.8, lot 2)."""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.ports.riposte_store_port import FollowerPosition

_NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


class TestSqliteRiposteStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "var" / "lib" / "riposte.sqlite3"
        self.connection = open_riposte_connection(self.path)
        self.store = SqliteRiposteStore(self.connection)

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def test_schema_version_is_recorded(self):
        row = self.connection.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        self.assertEqual(row[0], "1")

    def test_position_round_trip_and_update(self):
        self.assertIsNone(self.store.get_position("waf"))
        first = FollowerPosition(inode=1, device=2, offset=10, fingerprint="abc", fingerprint_length=10)
        self.store.save_position("waf", first)
        self.assertEqual(self.store.get_position("waf"), first)
        second = FollowerPosition(inode=1, device=2, offset=99, fingerprint="abc", fingerprint_length=10)
        self.store.save_position("waf", second)
        self.assertEqual(self.store.get_position("waf"), second)

    def test_event_is_new_only_once(self):
        self.assertTrue(self.store.mark_seen("waf:r1", _NOW))
        self.assertFalse(self.store.mark_seen("waf:r1", _NOW))

    def test_seen_events_are_purged_by_age(self):
        self.store.mark_seen("old", _NOW - timedelta(days=40))
        self.store.mark_seen("recent", _NOW)
        self.assertEqual(self.store.purge_seen_before(_NOW - timedelta(days=31)), 1)
        self.assertTrue(self.store.mark_seen("old", _NOW))  # oublie, donc de nouveau « nouveau »
        self.assertFalse(self.store.mark_seen("recent", _NOW))

    def test_state(self):
        self.assertIsNone(self.store.get_state("emergency_stop"))
        self.store.set_state("emergency_stop", "1")
        self.store.set_state("emergency_stop", "0")
        self.assertEqual(self.store.get_state("emergency_stop"), "0")

    def test_audit_is_bounded_by_age_and_rows(self):
        for i in range(10):
            self.store.append_audit(_NOW - timedelta(days=100 - i), "old", str(i))
        for i in range(10):
            self.store.append_audit(_NOW, "recent", str(i))
        self.store.purge_audit(_NOW - timedelta(days=30), max_rows=5)
        rows = self.connection.execute("SELECT kind, detail FROM audit ORDER BY id").fetchall()
        self.assertEqual(rows, [("recent", str(i)) for i in range(5, 10)])

    def test_read_only_connection_never_creates_a_database(self):
        missing = Path(self._tmp.name) / "absent.sqlite3"
        with self.assertRaises(OSError):
            open_riposte_connection(missing, read_only=True)
        self.assertFalse(missing.exists())

    def test_read_only_connection_sees_written_data_and_cannot_write(self):
        self.store.set_state("k", "v")
        reader = open_riposte_connection(self.path, read_only=True)
        try:
            self.assertEqual(SqliteRiposteStore(reader).get_state("k"), "v")
            with self.assertRaises(sqlite3.OperationalError):  # « attempt to write a readonly database »
                SqliteRiposteStore(reader).set_state("k", "w")
        finally:
            reader.close()


if __name__ == "__main__":
    unittest.main()
