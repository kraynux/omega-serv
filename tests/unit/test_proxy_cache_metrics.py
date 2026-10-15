import unittest

from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics


class TestProxyCacheMetrics(unittest.TestCase):
    def test_fresh_metrics_are_zero(self):
        self.assertEqual(ProxyCacheMetrics().snapshot("/api/"), (0, 0))
        self.assertEqual(ProxyCacheMetrics().snapshot(), (0, 0))

    def test_records_hits_and_misses_per_zone(self):
        metrics = ProxyCacheMetrics()
        metrics.record_hit("/api/")
        metrics.record_hit("/api/")
        metrics.record_miss("/api/")
        self.assertEqual(metrics.snapshot("/api/"), (2, 1))

    def test_zones_are_independent(self):
        metrics = ProxyCacheMetrics()
        metrics.record_hit("/api/")
        metrics.record_miss("/other/")
        self.assertEqual(metrics.snapshot("/api/"), (1, 0))
        self.assertEqual(metrics.snapshot("/other/"), (0, 1))

    def test_unknown_zone_is_zero(self):
        metrics = ProxyCacheMetrics()
        metrics.record_hit("/api/")
        self.assertEqual(metrics.snapshot("/never-seen/"), (0, 0))

    def test_global_snapshot_sums_every_zone(self):
        metrics = ProxyCacheMetrics()
        metrics.record_hit("/api/")
        metrics.record_hit("/api/")
        metrics.record_miss("/other/")
        self.assertEqual(metrics.snapshot(), (2, 1))


if __name__ == "__main__":
    unittest.main()
