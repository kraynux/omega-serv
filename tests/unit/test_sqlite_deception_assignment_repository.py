"""plan_active_defense_omega_serv.md, Phase 3 - vraie I/O reelle contre
un fichier sqlite temporaire, meme discipline que
test_sqlite_incident_repository.py."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import DeceptionAssignment
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_deception_assignment_repository import (
    SqliteDeceptionAssignmentRepository,
)

_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class TestSqliteDeceptionAssignmentRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.database_path = Path(self._tmp.name) / "active-defense.sqlite3"
        self.connection = open_active_defense_connection(self.database_path)
        self.repository = SqliteDeceptionAssignmentRepository(self.connection)

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def _assignment(self, **overrides) -> DeceptionAssignment:
        defaults = {
            "subject_id": "203.0.113.1:abcd", "profile_name": "fake_admin",
            "assigned_at": _NOW, "expires_at": _NOW + timedelta(hours=2),
        }
        defaults.update(overrides)
        return DeceptionAssignment(**defaults)

    def test_get_missing_assignment_returns_none(self):
        self.assertIsNone(self.repository.get("does-not-exist"))

    def test_save_then_get_round_trips(self):
        assignment = self._assignment()
        self.repository.save(assignment)
        self.assertEqual(self.repository.get(assignment.subject_id), assignment)

    def test_save_upserts_the_same_subject(self):
        self.repository.save(self._assignment(profile_name="fake_admin"))
        updated = self._assignment(profile_name="fake_cms", expires_at=_NOW + timedelta(hours=4))
        self.repository.save(updated)
        stored = self.repository.get(updated.subject_id)
        assert stored is not None
        self.assertEqual(stored.profile_name, "fake_cms")
        self.assertEqual(len(self.repository.list_active()), 1)

    def test_release_removes_the_assignment(self):
        assignment = self._assignment()
        self.repository.save(assignment)
        self.repository.release(assignment.subject_id)
        self.assertIsNone(self.repository.get(assignment.subject_id))

    def test_release_missing_subject_is_a_no_op(self):
        self.repository.release("does-not-exist")  # ne leve jamais

    def test_list_active_returns_all_stored_rows_including_expired(self):
        self.repository.save(self._assignment(subject_id="s1", expires_at=_NOW - timedelta(hours=1)))
        self.repository.save(self._assignment(subject_id="s2", expires_at=_NOW + timedelta(hours=1)))
        subjects = {a.subject_id for a in self.repository.list_active()}
        self.assertEqual(subjects, {"s1", "s2"})


if __name__ == "__main__":
    unittest.main()
