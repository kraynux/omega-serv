"""Sonde reelle (psutil) - meme discipline que
tests/unit/test_openssl_certificate_tool.py : verifie la forme du
resultat contre le systeme reel, aucun mock d'une bibliotheque dont le
seul travail est de lire de vraies statistiques systeme."""
import tempfile
import unittest
from pathlib import Path

import psutil

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


class TestServerStats(unittest.TestCase):
    def test_own_process_logs_and_free_space(self):
        import os
        import tempfile
        from pathlib import Path

        from omega_serv.infrastructure.probe.system_stats import collect_server_stats

        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "log"
            (logs / "remote").mkdir(parents=True)
            (logs / "access.log").write_bytes(b"x" * 300)
            (logs / "remote" / "b.log").write_bytes(b"x" * 500)
            stats = collect_server_stats(os.getpid(), 1, logs, Path(tmp))
            self.assertTrue(stats["running"])
            self.assertGreaterEqual(stats["process_count"], 1)
            self.assertGreater(stats["rss"], 0)
            self.assertEqual(stats["log_total"], 800)
            self.assertEqual((stats["log_largest_name"], stats["log_largest_size"]), ("remote/b.log", 500))
            self.assertGreater(stats["state_total"], 0)
            stopped = collect_server_stats(None, 1, logs / "absent", Path(tmp))
            self.assertFalse(stopped["running"])
            self.assertEqual(stopped["log_total"], 0)


class TestNetworkLinks(unittest.TestCase):
    """Interfaces de l'ecran Etat & Ressources (2026-11-05) : nos propres constantes de chemin
    (/proc/net/route, /sys/class/net) substituees, psutil jamais mocke."""

    def setUp(self):
        self._originals = (system_stats._PROC_NET_ROUTE, system_stats._SYS_CLASS_NET)
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        system_stats._PROC_NET_ROUTE, system_stats._SYS_CLASS_NET = self._originals
        self._tmp.cleanup()

    def test_default_interface_is_the_lowest_metric_default_route(self):
        route = self.root / "route"
        route.write_text(
            "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n"
            "wlp2s0\t00000000\t0101A8C0\t0003\t0\t0\t600\t00000000\n"
            "enp4s0\t0001A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\n"
            "enp4s0\t00000000\t0101A8C0\t0003\t0\t0\t100\t00000000\n")
        system_stats._PROC_NET_ROUTE = route
        self.assertEqual(system_stats._detect_default_interface(), "enp4s0")

    def test_no_route_file_means_unknown(self):
        system_stats._PROC_NET_ROUTE = self.root / "absent"
        self.assertEqual(system_stats._detect_default_interface(), "")

    def test_only_physical_cards_with_their_kind(self):
        names = list(psutil.net_if_stats())
        system_stats._SYS_CLASS_NET = self.root
        (self.root / names[0] / "device").mkdir(parents=True)
        if len(names) > 1:
            (self.root / names[1] / "device").mkdir(parents=True)
            (self.root / names[1] / "wireless").mkdir()
        links = system_stats._physical_links({names[0]: "10.0.0.2"})
        self.assertEqual([link["name"] for link in links], sorted(names[:2]))
        by_name = {link["name"]: link for link in links}
        self.assertEqual(by_name[names[0]]["kind"], "ethernet")
        self.assertEqual(by_name[names[0]]["ip"], "10.0.0.2")
        if len(names) > 1:
            self.assertEqual(by_name[names[1]]["kind"], "wifi")


class TestPacketTotals(unittest.TestCase):
    def setUp(self):
        self._original = system_stats._PROC_NET_SNMP
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        system_stats._PROC_NET_SNMP = self._original
        self._tmp.cleanup()

    def test_tcp_segments_and_udp_datagrams_in_plus_out(self):
        snmp = Path(self._tmp.name) / "snmp"
        snmp.write_text(
            "Ip: Forwarding DefaultTTL\nIp: 1 64\n"
            "Tcp: RtoAlgorithm InSegs OutSegs\nTcp: 1 100 50\n"
            "Udp: InDatagrams NoPorts OutDatagrams\nUdp: 30 0 12\n")
        system_stats._PROC_NET_SNMP = snmp
        self.assertEqual(system_stats._read_packet_totals(), (150, 42))

    def test_unreadable_file_means_unknown(self):
        system_stats._PROC_NET_SNMP = Path(self._tmp.name) / "absent"
        self.assertIsNone(system_stats._read_packet_totals())
