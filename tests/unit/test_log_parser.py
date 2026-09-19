"""Teste compute_log_stats (infrastructure/logging/log_parser.py) contre
un vrai fichier temporaire au format combine."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.infrastructure.logging.log_parser import compute_log_stats

_NOW = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)


def _line(ip: str, hour: int, status: int) -> str:
    return f'{ip} - - [08/Sep/2026:{hour:02d}:00:00 +0000] "GET / HTTP/1.1" {status} 10 "-" "curl"\n'


class TestComputeLogStats(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "access.log"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty_summary(self):
        summary = compute_log_stats(self.path, "24h", now=_NOW)
        self.assertEqual(summary.total_requests, 0)
        self.assertEqual(summary.top_ips, ())
        self.assertEqual(summary.status_code_counts, {})
        self.assertEqual(summary.hourly_counts, (0,) * 24)

    def test_aggregates_counts_status_and_top_ips(self):
        self.path.write_text(
            _line("1.1.1.1", 10, 200)
            + _line("1.1.1.1", 11, 200)
            + _line("2.2.2.2", 11, 404)
        )
        summary = compute_log_stats(self.path, "24h", now=_NOW)
        self.assertEqual(summary.total_requests, 3)
        self.assertEqual(summary.status_code_counts, {200: 2, 404: 1})
        self.assertEqual(summary.top_ips[0].ip, "1.1.1.1")
        self.assertEqual(summary.top_ips[0].count, 2)
        self.assertEqual(summary.hourly_counts[10], 1)
        self.assertEqual(summary.hourly_counts[11], 2)

    def test_entries_outside_period_are_excluded(self):
        old_line = '1.1.1.1 - - [01/Jan/2020:00:00:00 +0000] "GET / HTTP/1.1" 200 10 "-" "curl"\n'
        self.path.write_text(old_line + _line("2.2.2.2", 10, 200))
        summary = compute_log_stats(self.path, "24h", now=_NOW)
        self.assertEqual(summary.total_requests, 1)

    def test_unparseable_lines_are_ignored(self):
        self.path.write_text("garbage line\n" + _line("1.1.1.1", 10, 200))
        summary = compute_log_stats(self.path, "24h", now=_NOW)
        self.assertEqual(summary.total_requests, 1)

    def test_unknown_period_defaults_to_24h(self):
        self.path.write_text(_line("1.1.1.1", 10, 200))
        summary = compute_log_stats(self.path, "unknown", now=_NOW)
        self.assertEqual(summary.total_requests, 1)

    def test_top_ips_limited_to_twenty(self):
        content = "".join(_line(f"10.0.0.{i}", 10, 200) for i in range(25))
        self.path.write_text(content)
        summary = compute_log_stats(self.path, "24h", now=_NOW)
        self.assertEqual(len(summary.top_ips), 20)
        self.assertEqual(summary.total_requests, 25)


if __name__ == "__main__":
    unittest.main()
