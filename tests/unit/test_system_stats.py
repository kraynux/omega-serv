"""Sonde reelle (psutil) - meme discipline que
tests/unit/test_openssl_certificate_tool.py : verifie la forme du
resultat contre le systeme reel, aucun mock d'une bibliotheque dont le
seul travail est de lire de vraies statistiques systeme."""
import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.probe import system_stats
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


class TestCollectSystemStatsMalformedResolvConf(unittest.TestCase):
    """Retour utilisateur 2026-09-26 (Archcraft) : IndexError reel en
    usage sur une ligne "nameserver" sans adresse a la suite
    (/etc/resolv.conf partiellement genere/malforme, ex. systemd-resolved
    ou NetworkManager) - remontait jusqu'au worker Textual de l'ecran
    Etat & Ressources (gel avant le passage en worker, toast d'erreur
    generique depuis). `_RESOLV_CONF` est NOTRE propre constante de
    chemin (pas psutil) - la substituer ici reste dans la discipline du
    module (verifier notre logique de parsing contre un vrai fichier,
    jamais mocker psutil lui-meme)."""

    def setUp(self):
        self._original_resolv_conf = system_stats._RESOLV_CONF
        self._tmp = Path(tempfile.mktemp())

    def tearDown(self):
        system_stats._RESOLV_CONF = self._original_resolv_conf
        self._tmp.unlink(missing_ok=True)

    def test_nameserver_line_without_address_is_skipped_not_raised(self):
        self._tmp.write_text("nameserver\nnameserver 1.1.1.1\n")
        system_stats._RESOLV_CONF = self._tmp

        stats = collect_system_stats()

        self.assertEqual(stats["dns"], ["1.1.1.1"])


if __name__ == "__main__":
    unittest.main()
