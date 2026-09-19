"""plan_active_defense_omega_serv.md, Phase 1 - vraie I/O reelle contre
un fichier sqlite temporaire, jamais de FilesystemPort/sqlite3 simule
(meme discipline que test_json_instance_registry.py)."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import ThreatState
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
    SqliteThreatStateRepository,
)

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class TestSqliteThreatStateRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.database_path = Path(self._tmp.name) / "var" / "lib" / "active-defense.sqlite3"
        self.connection = open_active_defense_connection(self.database_path)
        self.repository = SqliteThreatStateRepository(self.connection)

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def _state(self, **overrides) -> ThreatState:
        defaults = {
            "subject_id": "203.0.113.42:abc123", "score": 40, "level": "suspicious",
            "updated_at": _NOW, "expires_at": _NOW + timedelta(hours=2), "active_actions": (),
        }
        defaults.update(overrides)
        return ThreatState(**defaults)

    def test_creates_parent_directory(self):
        self.assertTrue(self.database_path.parent.is_dir())
        self.assertTrue(self.database_path.exists())

    def test_get_missing_subject_returns_none(self):
        self.assertIsNone(self.repository.get("does-not-exist"))

    def test_save_then_get_round_trips(self):
        state = self._state(active_actions=("enrich_log", "delay"))
        self.repository.save(state)
        loaded = self.repository.get(state.subject_id)
        self.assertEqual(loaded, state)

    def test_save_upserts_existing_subject(self):
        self.repository.save(self._state(score=10, level="normal"))
        self.repository.save(self._state(score=90, level="hostile"))
        loaded = self.repository.get("203.0.113.42:abc123")
        assert loaded is not None
        self.assertEqual(loaded.score, 90)
        self.assertEqual(loaded.level, "hostile")

    def test_save_writes_an_audit_log_entry(self):
        self.repository.save(self._state())
        row = self.connection.execute("SELECT COUNT(*) FROM active_defense_audit_log").fetchone()
        self.assertEqual(row[0], 1)

    def test_expire_before_removes_only_expired_entries(self):
        self.repository.save(self._state(subject_id="expired", expires_at=_NOW - timedelta(seconds=1)))
        self.repository.save(self._state(subject_id="still-valid", expires_at=_NOW + timedelta(hours=1)))
        removed = self.repository.expire_before(_NOW)
        self.assertEqual(removed, 1)
        self.assertIsNone(self.repository.get("expired"))
        self.assertIsNotNone(self.repository.get("still-valid"))

    def test_list_all_sorted_by_score_descending(self):
        self.repository.save(self._state(subject_id="low", score=10, level="normal"))
        self.repository.save(self._state(subject_id="high", score=90, level="hostile"))
        self.repository.save(self._state(subject_id="mid", score=40, level="suspicious"))
        subjects = [s.subject_id for s in self.repository.list_all()]
        self.assertEqual(subjects, ["high", "mid", "low"])

    def test_re_opening_the_same_database_file_preserves_data(self):
        self.repository.save(self._state())
        self.connection.close()
        reopened = open_active_defense_connection(self.database_path)
        try:
            reloaded = SqliteThreatStateRepository(reopened).get("203.0.113.42:abc123")
            self.assertIsNotNone(reloaded)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
