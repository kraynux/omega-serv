"""Service lance avec un code anterieur a la mise a jour installee (retour
utilisateur 2026-10-26, craftdark : rechargement annonce "reussi" mais
nouveaux reglages sans effet tant que le service n'etait pas redemarre)."""
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.services.check_stale_service import service_runs_older_code
from omega_serv.domain.services.stale_service import runs_older_code
from omega_serv.infrastructure.process.process_info import newest_code_time, process_start_time

_T0 = datetime(2026, 10, 26, 11, 0, tzinfo=timezone.utc)


class _Manager:
    def __init__(self, pid):
        self._pid = pid

    def main_pid(self, service_name):
        if isinstance(self._pid, Exception):
            raise self._pid
        return self._pid


class TestRunsOlderCode(unittest.TestCase):
    def test_started_before_update_is_stale(self):
        self.assertTrue(runs_older_code(_T0, _T0 + timedelta(minutes=5)))

    def test_started_after_update_is_fine(self):
        self.assertFalse(runs_older_code(_T0 + timedelta(minutes=5), _T0))

    def test_rounding_margin_of_two_seconds(self):
        self.assertFalse(runs_older_code(_T0, _T0 + timedelta(seconds=2)))
        self.assertTrue(runs_older_code(_T0, _T0 + timedelta(seconds=3)))


class TestServiceRunsOlderCode(unittest.TestCase):
    def _check(self, pid, started_at, code_time):
        return service_runs_older_code(_Manager(pid), "omega-serv", lambda _pid: started_at, code_time)

    def test_stale_service_detected(self):
        self.assertTrue(self._check(1234, _T0, _T0 + timedelta(hours=1)))

    def test_any_missing_information_never_warns(self):
        later = _T0 + timedelta(hours=1)
        self.assertFalse(self._check(None, _T0, later))          # service arrete / OpenRC
        self.assertFalse(self._check(1234, None, later))         # /proc illisible
        self.assertFalse(self._check(1234, _T0, None))           # code introuvable
        self.assertFalse(self._check(RuntimeError("bus"), _T0, later))  # gestionnaire en erreur


class TestProcessInfo(unittest.TestCase):
    def test_own_process_start_time_is_in_the_past_and_recent(self):
        started_at = process_start_time(os.getpid())
        self.assertIsNotNone(started_at)
        age = datetime.now(timezone.utc) - started_at
        self.assertGreaterEqual(age.total_seconds(), -1)
        self.assertLess(age, timedelta(days=1))

    def test_unknown_pid_gives_none(self):
        self.assertIsNone(process_start_time(2**30))

    def test_newest_code_time_is_the_latest_py_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            old, new = root / "a.py", root / "sub" / "b.py"
            old.write_text("")
            new.write_text("")
            (root / "notes.txt").write_text("")
            now = time.time()
            os.utime(old, (now - 3600, now - 3600))
            os.utime(new, (now - 60, now - 60))
            os.utime(root / "notes.txt", (now, now))
            self.assertAlmostEqual(newest_code_time(root).timestamp(), now - 60, delta=1)

    def test_empty_package_gives_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(newest_code_time(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
