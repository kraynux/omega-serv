# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.domain.logging.access_log_parser import ParsedAccessLogEntry
from omega_serv.domain.logging.live_traffic_stats import LiveTrafficBuffer


def _entry(ip: str, status: int, size: int = 100) -> ParsedAccessLogEntry:
    return ParsedAccessLogEntry(ip=ip, timestamp=datetime.now(timezone.utc), status_code=status, response_size=size)


class TestLiveTrafficBuffer(unittest.TestCase):
    def test_empty_buffer_returns_zeroed_stats(self):
        started_at = datetime.now(timezone.utc)
        buffer = LiveTrafficBuffer(started_at)
        stats = buffer.get_stats(started_at + timedelta(seconds=10))
        self.assertEqual(stats.total, 0)
        self.assertEqual(stats.unique_ips, 0)
        self.assertEqual(stats.top_ip, "N/A")
        self.assertEqual(stats.error_rate, 0.0)
        self.assertEqual(stats.rps, 0.0)

    def test_status_code_breakdown(self):
        started_at = datetime.now(timezone.utc)
        buffer = LiveTrafficBuffer(started_at)
        buffer.add(_entry("1.1.1.1", 200))
        buffer.add(_entry("1.1.1.1", 301))
        buffer.add(_entry("1.1.1.1", 404))
        buffer.add(_entry("1.1.1.1", 500))
        stats = buffer.get_stats(started_at + timedelta(seconds=1))
        self.assertEqual(stats.total, 4)
        self.assertEqual(stats.success_2xx, 1)
        self.assertEqual(stats.redirect_3xx, 1)
        self.assertEqual(stats.errors_4xx, 1)
        self.assertEqual(stats.errors_5xx, 1)
        self.assertEqual(stats.error_rate, 50.0)

    def test_unique_ips_and_top_ip(self):
        started_at = datetime.now(timezone.utc)
        buffer = LiveTrafficBuffer(started_at)
        buffer.add(_entry("1.1.1.1", 200))
        buffer.add(_entry("1.1.1.1", 200))
        buffer.add(_entry("2.2.2.2", 200))
        stats = buffer.get_stats(started_at + timedelta(seconds=1))
        self.assertEqual(stats.unique_ips, 2)
        self.assertEqual(stats.top_ip, "1.1.1.1")

    def test_rps_and_bps_computed_over_elapsed_time(self):
        started_at = datetime.now(timezone.utc)
        buffer = LiveTrafficBuffer(started_at)
        for _ in range(10):
            buffer.add(_entry("1.1.1.1", 200, size=100))
        stats = buffer.get_stats(started_at + timedelta(seconds=10))
        self.assertAlmostEqual(stats.rps, 1.0, places=2)
        self.assertAlmostEqual(stats.bps, 100.0, places=2)
        self.assertEqual(stats.bytes_total, 1000)
        self.assertEqual(stats.avg_size, 100.0)

    def test_elapsed_time_floored_to_avoid_division_by_zero(self):
        started_at = datetime.now(timezone.utc)
        buffer = LiveTrafficBuffer(started_at)
        buffer.add(_entry("1.1.1.1", 200))
        stats = buffer.get_stats(started_at)  # aucun temps ecoule
        self.assertGreater(stats.rps, 0.0)  # ne leve pas ZeroDivisionError

    def test_buffer_size_bounded_by_max_size(self):
        started_at = datetime.now(timezone.utc)
        buffer = LiveTrafficBuffer(started_at, max_size=3)
        for i in range(10):
            buffer.add(_entry(f"1.1.1.{i}", 200))
        stats = buffer.get_stats(started_at + timedelta(seconds=1))
        self.assertEqual(stats.buffer_size, 3)
        self.assertEqual(stats.total, 10)  # les compteurs cumules restent corrects


if __name__ == "__main__":
    unittest.main()
