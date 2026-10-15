import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.logs.reading import read_entries, read_entries_for_paths


def _line(days_ago: int) -> str:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'1.2.3.4 - - [{ts}] "GET / HTTP/1.1" 200 12'


class TestReadEntries(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(read_entries(str(self.root / "missing.log")), [])

    def test_reads_and_parses_all_lines(self):
        path = self.root / "a.log"
        path.write_text(_line(0) + "\n" + _line(1) + "\n")
        entries = read_entries(str(path))
        self.assertEqual(len(entries), 2)


class TestReadEntriesForPaths(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_period_reads_everything(self):
        path = self.root / "a.log"
        path.write_text(_line(0) + "\n" + _line(60) + "\n")
        entries = read_entries_for_paths([str(path)])
        self.assertEqual(len(entries), 2)

    def test_period_24h_excludes_older_lines(self):
        path = self.root / "a.log"
        path.write_text(_line(0) + "\n" + _line(10) + "\n")
        entries = read_entries_for_paths([str(path)], period="24h")
        self.assertEqual(len(entries), 1)

    def test_period_7d_keeps_recent_lines(self):
        path = self.root / "a.log"
        path.write_text(_line(1) + "\n" + _line(3) + "\n" + _line(60) + "\n")
        entries = read_entries_for_paths([str(path)], period="7d")
        self.assertEqual(len(entries), 2)

    def test_multiple_paths_are_combined(self):
        path_a = self.root / "a.log"
        path_b = self.root / "b.log"
        path_a.write_text(_line(0) + "\n")
        path_b.write_text(_line(0) + "\n")
        entries = read_entries_for_paths([str(path_a), str(path_b)])
        self.assertEqual(len(entries), 2)

    def test_missing_path_in_the_middle_does_not_abort_the_others(self):
        path_a = self.root / "a.log"
        path_a.write_text(_line(0) + "\n")
        entries = read_entries_for_paths([str(path_a), str(self.root / "missing.log")], period="24h")
        self.assertEqual(len(entries), 1)


if __name__ == "__main__":
    unittest.main()
