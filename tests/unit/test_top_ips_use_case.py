import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.logs.top_ips import compute_top_ips_for_paths


def _access_line(ip: str, days_ago: int = 0) -> str:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'{ip} - - [{ts}] "GET / HTTP/1.1" 200 12'


class TestComputeTopIpsForPaths(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_counts_across_a_single_file(self):
        path = self.root / "access.log"
        path.write_text("\n".join([_access_line("1.1.1.1"), _access_line("1.1.1.1"), _access_line("2.2.2.2")]))
        top = compute_top_ips_for_paths([str(path)])
        self.assertEqual(top[0].ip, "1.1.1.1")
        self.assertEqual(top[0].count, 2)

    def test_counts_across_multiple_files(self):
        path_a = self.root / "a.log"
        path_b = self.root / "b.log"
        path_a.write_text(_access_line("1.1.1.1"))
        path_b.write_text(_access_line("1.1.1.1"))
        top = compute_top_ips_for_paths([str(path_a), str(path_b)])
        self.assertEqual(top[0].count, 2)

    def test_period_filters_out_old_entries(self):
        path = self.root / "access.log"
        path.write_text("\n".join([_access_line("1.1.1.1", days_ago=0), _access_line("1.1.1.1", days_ago=60)]))
        top = compute_top_ips_for_paths([str(path)], period="24h")
        self.assertEqual(top[0].count, 1)

    def test_no_entries_returns_empty_list(self):
        path = self.root / "empty.log"
        path.write_text("")
        self.assertEqual(compute_top_ips_for_paths([str(path)]), [])


if __name__ == "__main__":
    unittest.main()
