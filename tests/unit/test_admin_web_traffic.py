# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Trafic des sites, lot 9b du tableau de bord web (plan §9.5 ; decision de l'auteur du 2026-11-17 : compteurs dans les
deux moteurs) : compteurs du noyau d'une socket (recu, confie au noyau), compteur d'un processus serveur (connexions
nees ici ou confiees par l'autre moteur), fichier publie, total lu par le processus d'administration."""
from __future__ import annotations

import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from omega_serv.infrastructure.admin_web.traffic_reader import TrafficTotals
from omega_serv.infrastructure.server.traffic_meter import (
    TRAFFIC_RELATIVE_DIR,
    TrafficFile,
    TrafficMeter,
    tcp_bytes,
)


class _Kernel:
    """Compteurs de sockets simulees : {socket: (recus, envoyes)}."""

    def __init__(self):
        self.values = {}

    def read(self, sock):
        return self.values.get(sock)


class TestSocketCounters(unittest.TestCase):
    def test_real_socket_counts_received_and_everything_handed_to_the_kernel(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        client = socket.create_connection(listener.getsockname())
        server, _address = listener.accept()
        try:
            client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            client.sendall(b"x" * 1000)
            deadline = time.monotonic() + 2
            while tcp_bytes(server)[0] < 1000 and time.monotonic() < deadline:
                time.sleep(0.01)
            server.setblocking(False)
            handed = 0
            try:
                while True:  # le client ne lit pas : une partie reste en file, jamais acquittee
                    handed += server.send(b"y" * 65536)
            except BlockingIOError:
                pass
            self.assertEqual(tcp_bytes(server), (1000, handed))
        finally:
            for sock in (client, server, listener):
                sock.close()
        self.assertIsNone(tcp_bytes(server))  # socket fermee
        self.assertIsNone(tcp_bytes(None))


class TestMeter(unittest.TestCase):
    def test_connections_born_here_count_from_zero_and_handed_ones_from_what_they_saw(self):
        kernel = _Kernel()
        meter = TrafficMeter(kernel.read)
        kernel.values = {"a": (300, 5000), "b": (1000, 9000)}
        meter.open(1, "a")  # nee ici : poignee de main TLS comprise
        meter.open(2, "b", from_start=False)  # confiee par le natif, qui a compte jusque-la
        self.assertEqual((meter.received, meter.sent), (300, 5000))
        kernel.values = {"a": (400, 15000), "b": (1100, 9500)}
        meter.sample_all()
        self.assertEqual((meter.received, meter.sent), (500, 15500))
        meter.close(1, unsent=2048)  # reste du tampon du transport : partira apres la fermeture
        meter.close(1)  # deja fermee : rien
        self.assertEqual(meter.sent, 17548)
        kernel.values = {"b": (1100, 9000)}  # jamais de recul
        meter.sample_all()
        self.assertEqual((meter.received, meter.sent), (500, 17548))
        self.assertTrue(meter.measured)

    def test_without_kernel_counters_nothing_is_measured(self):
        meter = TrafficMeter(lambda sock: None)
        meter.open(1, "a")
        meter.close(1, unsent=10)
        self.assertFalse(meter.measured)
        self.assertEqual((meter.received, meter.sent), (0, 0))


class TestFileAndTotals(unittest.TestCase):
    def test_file_is_written_at_most_every_5_seconds_and_removed(self):
        with tempfile.TemporaryDirectory() as name:
            file = TrafficFile(Path(name), pid=4242)
            file.publish(10, 20, now=100.0)
            file.publish(11, 21, now=102.0)  # trop tot
            self.assertEqual(json.loads(file.path.read_text()), {"recu": 10, "envoye": 20})
            file.publish(12, 22, now=105.0)
            self.assertEqual(json.loads(file.path.read_text())["envoye"], 22)
            self.assertEqual(file.path.stat().st_mode & 0o777, 0o640)
            file.publish(13, 23, now=105.5, force=True)
            self.assertEqual(json.loads(file.path.read_text())["recu"], 13)
            file.remove()
            file.remove()
            self.assertFalse(file.path.exists())
            os.chmod(name, 0o500)
            try:
                TrafficFile(Path(name) / "lecture-seule", pid=1).publish(1, 1)  # jamais d'exception
            finally:
                os.chmod(name, 0o700)

    def test_totals_add_live_processes_without_recounting_the_past(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            alive = {100, 200, 300}
            born = {100: 0.0, 200: 0.0, 300: 2000.0}
            now = [1000.0]
            totals = TrafficTotals(root, alive=lambda pid: pid in alive, clock=lambda: now[0], started_at=born.get)
            TrafficFile(root, pid=100).publish(5000, 90000, force=True)  # publiait deja : point de depart
            self.assertEqual(totals.read(), (0, 0))
            TrafficFile(root, pid=100).publish(6000, 100000, force=True)
            TrafficFile(root, pid=300).publish(10, 20, force=True)  # ne apres : compte depuis zero
            self.assertEqual(totals.read(), (1010, 10020))
            TrafficFile(root, pid=100).publish(50, 60, force=True)  # compteur reparti de zero
            self.assertEqual(totals.read(), (1010, 10020))
            TrafficFile(root, pid=100).publish(150, 160, force=True)
            self.assertEqual(totals.read(), (1110, 10120))
            (root / TRAFFIC_RELATIVE_DIR / "200.json").write_text("abime")
            (root / TRAFFIC_RELATIVE_DIR / "notes.json").write_text("{}")
            self.assertEqual(totals.read(), (1110, 10120))
            alive.discard(300)
            dead = root / TRAFFIC_RELATIVE_DIR / "300.json"
            self.assertEqual(totals.read(), (1110, 10120))
            self.assertTrue(dead.exists())  # mort depuis peu : garde
            os.utime(dead, (0, 0))
            now[0] = 10_000.0
            totals.read()
            self.assertFalse(dead.exists())  # plus d'une heure : retire
            alive.clear()
            self.assertEqual(totals.read(), (1110, 10120))  # serveur arrete : le total reste

    def test_a_server_that_publishes_after_the_first_read_counts_from_zero(self):
        """Essai de l'auteur du 2026-11-17 : serveur lance 4 s avant le processus d'administration, aucun visiteur
        encore ; le premier visiteur fait apparaitre le fichier : tout compte (avant : pris comme point de depart)."""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            totals = TrafficTotals(root, alive=lambda pid: True, clock=lambda: 1000.0, started_at=lambda pid: 996.0)
            self.assertIsNone(totals.read())  # aucun fichier jamais vu : pas de mesure
            TrafficFile(root, pid=100).publish(700, 15000, force=True)
            self.assertEqual(totals.read(), (700, 15000))


if __name__ == "__main__":
    unittest.main()
