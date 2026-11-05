"""Processus RIPOSTE, lot 2 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.1-3.2) : suivi des journaux,
dedoublonnage, positions, battement de coeur, etat, un seul processus par instance."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.riposte.follow_journals import FollowStats, JournalSource, follow_once
from omega_serv.application.riposte.get_status import get_riposte_status
from omega_serv.application.riposte.run_riposte import run_riposte
from omega_serv.domain.security.riposte.events import (
    parse_security_event_line,
    parse_waf_alert_line,
)
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.infrastructure.riposte.log_follower import LogFollower
from omega_serv.infrastructure.riposte.process_lock import ProcessLock


class _Clock:
    def __init__(self):
        self.value = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)

    def now(self):
        return self.value


def _waf_line(request_id, ip="203.0.113.7", stage="inspection", score=8):
    return json.dumps({
        "timestamp": "2026-11-01T10:00:00+00:00", "request_id": request_id, "remote_ip": ip, "action": "block",
        "stage": stage, "score": score, "rules": ["R"], "findings": [{"id": "R", "pack": "scan-paths"}],
    })


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.waf_log = self.root / "waf-alerts.log"
        self.security_log = self.root / "security-events.jsonl"
        self.connection = open_riposte_connection(self.root / "riposte.sqlite3")
        self.store = SqliteRiposteStore(self.connection)
        self.clock = _Clock()

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def _sources(self):
        return [
            JournalSource("waf", LogFollower(self.waf_log, self.store.get_position("waf")), parse_waf_alert_line),
            JournalSource("security", LogFollower(self.security_log, self.store.get_position("security")),
                          parse_security_event_line),
        ]

    def _append(self, path, *lines):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in lines))


class TestFollowOnce(_Base):
    def test_new_events_are_returned_once(self):
        sources = self._sources()
        stats = FollowStats()
        self._append(self.waf_log, _waf_line("r1"), _waf_line("r2", stage="blocklist", score=0), "illisible")
        events = follow_once(sources, self.store, self.clock, stats)
        self.assertEqual([e.kind for e in events], ["attack", "blocklist_hit"])
        self.assertEqual(stats.rejected["not_json"], 1)
        self.assertEqual(follow_once(sources, self.store, self.clock, stats), [])

    def test_a_rewritten_journal_is_never_counted_twice(self):
        sources = self._sources()
        stats = FollowStats()
        self._append(self.waf_log, _waf_line("r1"), _waf_line("r2"))
        follow_once(sources, self.store, self.clock, stats)
        tmp = self.root / "x.tmp"
        tmp.write_text(_waf_line("r2") + "\n" + _waf_line("r3") + "\n")
        os.replace(tmp, self.waf_log)  # « Voir et traiter IP » : r1 retire, nouvel inode
        events = follow_once(sources, self.store, self.clock, stats)
        self.assertEqual([e.event_id for e in events], ["waf:r3"])
        self.assertEqual(stats.duplicates, 1)

    def test_restart_resumes_where_it_stopped(self):
        stats = FollowStats()
        self._append(self.waf_log, "")  # journal deja present au premier suivi : on part de la fin
        follow_once(self._sources(), self.store, self.clock, stats)
        self._append(self.waf_log, _waf_line("r1"))
        follow_once(self._sources(), self.store, self.clock, stats)  # « redemarrage » : nouveaux lecteurs
        self._append(self.waf_log, _waf_line("r2"))
        events = follow_once(self._sources(), self.store, self.clock, stats)
        self.assertEqual([e.event_id for e in events], ["waf:r2"])


class TestRunAndStatus(_Base):
    def test_loop_writes_heartbeat_and_stats_then_stops(self):
        self._append(self.waf_log, "")
        turns = iter(range(3))
        received = []

        def should_stop():
            try:
                turn = next(turns)
            except StopIteration:
                return True
            if turn == 1:
                self._append(self.waf_log, _waf_line("r1"), _waf_line("r2"))
            return False

        run_riposte(
            self._sources(), self.store, self.clock, should_stop=should_stop, sleep=lambda _s: None,
            report_error=lambda _m: None, on_events=received.extend, pid=4242,
        )
        self.assertEqual([e.event_id for e in received], ["waf:r1", "waf:r2"])
        status = get_riposte_status(self.store, self.clock.now())
        self.assertTrue(status.running)
        self.assertEqual(status.pid, 4242)
        self.assertEqual(status.new_events, 2)
        self.assertFalse(status.emergency_stop)
        self.assertFalse(get_riposte_status(self.store, self.clock.now() + timedelta(minutes=1)).running)

    def test_a_database_error_never_stops_the_loop(self):
        errors = []
        turns = iter([False, False, True])

        class _FailingOnce:
            def __init__(self, inner):
                self.inner, self.failed = inner, False

            def __getattr__(self, name):
                return getattr(self.inner, name)

            def mark_seen(self, *args):
                if not self.failed:
                    self.failed = True
                    raise OSError("database is locked")
                return self.inner.mark_seen(*args)

        self._append(self.waf_log, "")
        sources = self._sources()
        self._append(self.waf_log, _waf_line("r1"))
        run_riposte(sources, _FailingOnce(self.store), self.clock, should_stop=lambda: next(turns),
                    sleep=lambda _s: None, report_error=errors.append)
        self.assertEqual(len(errors), 2)  # l'erreur, puis le retablissement
        self.assertIn("retabli", errors[1])


class TestProcessLock(unittest.TestCase):
    def test_only_one_owner_and_released_on_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run" / "riposte.lock"
            first, second = ProcessLock(path), ProcessLock(path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()


if __name__ == "__main__":
    unittest.main()
