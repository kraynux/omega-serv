"""Sonde reelle (psutil) - meme discipline que
tests/unit/test_openssl_certificate_tool.py : verifie la forme du
resultat contre le systeme reel, aucun mock d'une bibliotheque dont le
seul travail est de lire de vraies statistiques systeme."""
import unittest

from omega_serv.infrastructure.probe.system_stats import collect_system_stats


class TestCollectSystemStats(unittest.TestCase):
    def test_returns_expected_keys_with_plausible_values(self):
        stats = collect_system_stats()

        self.assertGreaterEqual(stats["cpu_percent"], 0.0)
        self.assertGreater(stats["mem_total"], 0)
        self.assertGreaterEqual(stats["mem_percent"], 0.0)
        self.assertLessEqual(stats["mem_percent"], 100.0)
        self.assertGreaterEqual(stats["swap_percent"], 0.0)
        self.assertGreaterEqual(stats["load_1"], 0.0)
        self.assertGreater(stats["num_processes"], 0)
        self.assertGreater(stats["uptime_seconds"], 0.0)
        self.assertGreater(stats["disk_total"], 0)
        self.assertGreaterEqual(stats["net_bytes_sent"], 0)
        self.assertGreaterEqual(stats["net_bytes_recv"], 0)
        self.assertGreaterEqual(stats["tcp_established"], 0)
        self.assertIsInstance(stats["user_names"], list)
        self.assertIsInstance(stats["interfaces"], list)
        self.assertIsInstance(stats["dns"], list)
        self.assertIsInstance(stats["gateway"], str)
        self.assertIsInstance(stats["outbound_ip"], str)
        self.assertIsInstance(stats["temps"], dict)
        self.assertIsInstance(stats["fans"], dict)


if __name__ == "__main__":
    unittest.main()
