"""Ecriture differee d'Active Defense (OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §3.6).

Garanties verifiees : une ecriture ne bloque jamais l'appelant (meme base verrouillee), elle est
visible tout de suite par les lectures du meme processus, elle finit en base quand le verrou est
relache, une erreur ne remonte jamais a l'appelant et n'est journalisee qu'une fois par serie,
la file est bornee, la purge des etats expires est automatique, l'arret est borne."""
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import DeceptionAssignment, ThreatState
from omega_serv.infrastructure.persistence.active_defense_write_behind import (
    SqliteActiveDefenseWriter,
    WriteBehindDeceptionAssignmentRepository,
    WriteBehindThreatStateRepository,
)
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_deception_assignment_repository import (
    SqliteDeceptionAssignmentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
    SqliteThreatStateRepository,
)

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


class _Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


def _state(subject: str, score: int = 10, at: datetime = NOW, ttl: int = 7200) -> ThreatState:
    return ThreatState(subject_id=subject, score=score, level="normal", updated_at=at,
                       expires_at=at + timedelta(seconds=ttl))


class _WriteBehindCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.database = Path(self._tmp.name) / "var/lib/active-defense.sqlite3"
        self.reader_connection = open_active_defense_connection(self.database, lock_timeout=0.05)
        self.messages: list[str] = []
        self.clock = _Clock()
        self.writer = self._writer()

    def _writer(self, **kwargs) -> SqliteActiveDefenseWriter:
        writer = SqliteActiveDefenseWriter(self.database, self.clock, retry_pause_seconds=0.05,
                                           lock_timeout_seconds=0.1, **kwargs)
        writer.set_error_reporter(self.messages.append)
        return writer

    def tearDown(self) -> None:
        self.writer.stop(2.0)
        self.reader_connection.close()
        self._tmp.cleanup()

    def _stored_states(self) -> list[ThreatState]:
        connection = open_active_defense_connection(self.database)
        try:
            return SqliteThreatStateRepository(connection).list_all()
        finally:
            connection.close()

    def _hold_exclusive_lock(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.execute("BEGIN EXCLUSIVE")
        return connection


class TestThreatStates(_WriteBehindCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = WriteBehindThreatStateRepository(SqliteThreatStateRepository(self.reader_connection), self.writer)

    def test_saved_state_is_readable_at_once_then_stored(self):
        self.repository.save(_state("203.0.113.7:ua", 20))
        self.assertEqual(self.repository.get("203.0.113.7:ua").score, 20)  # avant meme le demarrage du fil
        self.writer.start()
        self.assertTrue(self.writer.flush(5))
        self.assertEqual([s.score for s in self._stored_states()], [20])
        self.assertEqual(self.repository._pending, {})

    def test_newest_of_pending_and_stored_wins(self):
        self.writer.start()
        self.repository.save(_state("s", 50, NOW))
        self.assertTrue(self.writer.flush(5))
        older = _state("s", 10, NOW - timedelta(minutes=5))
        self.repository._pending["s"] = older
        self.assertEqual(self.repository.get("s").score, 50)

    def test_locked_database_never_blocks_the_caller_and_nothing_is_lost(self):
        self.writer.start()
        lock = self._hold_exclusive_lock()
        try:
            started = time.perf_counter()
            for index in range(50):
                self.repository.save(_state(f"203.0.113.{index}:ua", index))
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, 0.2, "save() a attendu le verrou")
            self.assertEqual(self.repository.get("203.0.113.7:ua").score, 7)
            time.sleep(0.4)  # le fil essaie, echoue, annule le lot, reessaie
            self.assertEqual(len(self.repository._pending), 50, "un lot annule ne retire rien de l'en-attente")
        finally:
            lock.rollback()
            lock.close()
        self.assertTrue(self.writer.flush(5))
        self.assertEqual(len(self._stored_states()), 50)
        self.assertEqual(sum("écriture en base impossible" in m for m in self.messages), 1)
        self.assertEqual(sum("rétablie" in m for m in self.messages), 1)
        self.assertEqual(self.writer.dropped, 0)

    def test_full_queue_drops_counts_and_reports_once(self):
        writer = self._writer(max_pending=2)
        repository = WriteBehindThreatStateRepository(SqliteThreatStateRepository(self.reader_connection), writer)
        for index in range(5):
            repository.save(_state(f"s{index}"))
        self.assertEqual(writer.dropped, 3)
        self.assertEqual(sum("file d'écriture pleine" in m for m in self.messages), 1)
        self.assertEqual(set(repository._pending), {"s0", "s1"}, "un travail abandonne ne reste jamais en attente")
        writer.stop(1.0)

    def test_read_error_counts_as_unknown_and_is_reported_once(self):
        class _BrokenReader:
            def get(self, _subject):
                raise sqlite3.OperationalError("database is locked")

        repository = WriteBehindThreatStateRepository(_BrokenReader(), self.writer)
        self.assertIsNone(repository.get("x"))
        self.assertIsNone(repository.get("y"))
        repository.save(_state("x", 30))
        self.assertEqual(repository.get("x").score, 30)
        self.assertEqual(sum("lecture en base impossible" in m for m in self.messages), 1)

    def test_expired_states_are_purged_automatically(self):
        writer = self._writer(purge_interval_seconds=0.2)
        repository = WriteBehindThreatStateRepository(SqliteThreatStateRepository(self.reader_connection), writer)
        writer.start()
        repository.save(_state("old", ttl=60))
        repository.save(_state("fresh", ttl=7200))
        self.assertTrue(writer.flush(5))
        self.clock.current = NOW + timedelta(hours=1)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(self._stored_states()) != 1:
            time.sleep(0.05)
        self.assertEqual([s.subject_id for s in self._stored_states()], ["fresh"])
        writer.stop(1.0)

    def test_unexpected_job_error_never_kills_the_writer(self):
        self.writer.start()
        self.assertTrue(self.writer.submit(lambda _repositories: 1 / 0))
        self.repository.save(_state("after"))
        self.assertTrue(self.writer.flush(5))
        self.assertEqual([s.subject_id for s in self._stored_states()], ["after"])
        self.assertEqual(sum("erreur inattendue" in m for m in self.messages), 1)

    def test_stop_is_bounded_even_with_a_locked_database(self):
        self.writer.start()
        lock = self._hold_exclusive_lock()
        try:
            self.repository.save(_state("blocked"))
            time.sleep(0.2)
            started = time.perf_counter()
            self.writer.stop(1.0)
            self.assertLess(time.perf_counter() - started, 1.5)
        finally:
            lock.rollback()
            lock.close()
        self.assertFalse(self.writer.submit(lambda _repositories: None), "plus rien n'est accepte apres stop()")


class TestBatches(_WriteBehindCase):
    def test_a_large_burst_is_written_in_batches_and_fully_stored(self):
        repository = WriteBehindThreatStateRepository(SqliteThreatStateRepository(self.reader_connection), self.writer)
        for index in range(1000):
            repository.save(_state(f"b{index}", index))
        self.writer.start()
        self.assertTrue(self.writer.flush(10))
        self.assertEqual(len(self._stored_states()), 1000)
        self.assertEqual(repository._pending, {}, "tout est retire de l'en-attente une fois valide")


class TestAuditLogPruning(_WriteBehindCase):
    """Decision utilisateur 2026-10-26 : le journal d'audit n'etait jamais purge (trou de securite :
    un attaquant changeant d'adresse a chaque requete pouvait remplir le disque)."""

    def _audit_rows(self) -> list[str]:
        connection = open_active_defense_connection(self.database)
        try:
            return [row[0] for row in connection.execute("SELECT subject_id FROM active_defense_audit_log ORDER BY id")]
        finally:
            connection.close()

    def test_old_rows_then_rows_beyond_the_cap_are_removed_newest_kept(self):
        repository = SqliteThreatStateRepository(self.reader_connection)
        repository.save_many([_state("ancien", at=NOW - timedelta(days=40))])
        repository.save_many([_state(f"r{i}", at=NOW - timedelta(minutes=10 - i)) for i in range(10)])
        removed = repository.prune_audit_log(NOW - timedelta(days=30), max_rows=3)
        self.assertEqual(removed, 8)
        self.assertEqual(self._audit_rows(), ["r7", "r8", "r9"])

    def test_nothing_removed_when_recent_and_under_the_cap(self):
        repository = SqliteThreatStateRepository(self.reader_connection)
        repository.save_many([_state(f"r{i}") for i in range(5)])
        self.assertEqual(repository.prune_audit_log(NOW - timedelta(days=30), max_rows=200_000), 0)
        self.assertEqual(len(self._audit_rows()), 5)

    def test_automatic_purge_also_prunes_the_audit_log(self):
        writer = self._writer(purge_interval_seconds=0.2)
        repository = WriteBehindThreatStateRepository(SqliteThreatStateRepository(self.reader_connection), writer)
        writer.start()
        repository.save(_state("vieux", at=NOW - timedelta(days=45), ttl=10**8))
        self.assertTrue(writer.flush(5))
        self.assertEqual(self._audit_rows(), ["vieux"])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and self._audit_rows():
            time.sleep(0.05)
        self.assertEqual(self._audit_rows(), [])
        writer.stop(1.0)


class TestTrackedSubjectsCap(_WriteBehindCase):
    """Decision utilisateur 2026-10-26 : plafond des sources suivies, « normal » les plus
    anciennes supprimees d'abord, suspectes/hostiles gardees tant que possible."""

    def _hostile(self, subject: str, at: datetime) -> ThreatState:
        return ThreatState(subject_id=subject, score=80, level="hostile", updated_at=at,
                           expires_at=at + timedelta(hours=2))

    def test_normal_oldest_first_then_oldest_of_any_level(self):
        repository = SqliteThreatStateRepository(self.reader_connection)
        repository.save_many([self._hostile(f"h{i}", NOW - timedelta(hours=1, minutes=i)) for i in range(3)])
        repository.save_many([_state(f"n{i}", at=NOW - timedelta(minutes=10 - i)) for i in range(5)])
        self.assertEqual(repository.cap_tracked_subjects(5), 3)
        self.assertEqual({s.subject_id for s in self._stored_states()}, {"h0", "h1", "h2", "n3", "n4"})
        self.assertEqual(repository.cap_tracked_subjects(2), 3)
        self.assertEqual({s.subject_id for s in self._stored_states()}, {"h0", "h1"})
        self.assertEqual(repository.cap_tracked_subjects(200_000), 0)


class TestDeceptionAssignments(_WriteBehindCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = WriteBehindDeceptionAssignmentRepository(
            SqliteDeceptionAssignmentRepository(self.reader_connection), self.writer,
        )

    def _assignment(self, subject: str) -> DeceptionAssignment:
        return DeceptionAssignment(subject_id=subject, profile_name="fake_admin", assigned_at=NOW,
                                   expires_at=NOW + timedelta(hours=2))

    def test_save_then_release_are_visible_at_once_and_stored(self):
        self.repository.save(self._assignment("s"))
        self.assertEqual(self.repository.get("s").profile_name, "fake_admin")
        self.writer.start()
        self.assertTrue(self.writer.flush(5))
        self.repository.release("s")
        self.assertIsNone(self.repository.get("s"), "une liberation en attente masque la base")
        self.assertTrue(self.writer.flush(5))
        self.assertIsNone(self.repository.get("s"))
        self.assertEqual(self.repository._pending, {})


class TestConcurrentSaves(_WriteBehindCase):
    def test_many_threads_saving_never_lose_the_latest_state(self):
        repository = WriteBehindThreatStateRepository(SqliteThreatStateRepository(self.reader_connection), self.writer)
        self.writer.start()

        def save_many(prefix: str) -> None:
            for index in range(200):
                repository.save(_state(f"{prefix}{index % 20}", index, NOW + timedelta(seconds=index)))

        threads = [threading.Thread(target=save_many, args=(p,)) for p in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(self.writer.flush(5))
        stored = {s.subject_id: s.score for s in self._stored_states()}
        self.assertEqual(len(stored), 40)
        self.assertEqual(stored["a19"], 199)


if __name__ == "__main__":
    unittest.main()
