# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Historique du tableau de bord web, lots 7 et 9 (plan §8 et §9.5) : debits entre deux releves, paliers de taille fixe
(10 s a 2 h), moyenne et max des minutes, plages 1 h a 30 jours, fichier a colonnes relu (invalide ou trop vieux
ignore, format 1 repris), comptage des lignes du journal d'acces (rotation comprise), sonde, enregistreur, vue et API
de la page, reglage `history`."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.admin_web.history import HistoryRecorder
from omega_serv.application.admin_web.web_app import AdminWebApp
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.history import (
    SERIES,
    TIERS,
    Counters,
    HistoryRings,
    point_between,
)
from omega_serv.domain.admin_web.settings import AdminWebSettings, validate_admin_web
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.infrastructure.admin_web.history_probe import (
    HistoryProbe,
    LineCounter,
    ProcessTreeCpu,
    cpu_temperature,
)
from tests.unit import test_admin_web_auth as _web
from tests.unit.test_admin_web_auth import _auth, _Clock, _Store

T0 = 1_800_000_000  # multiple de 300 : debut d'une tranche de 5 min


def _counters(at, busy=0.0, total=0.0, mem=40.0, recv=0, sent=0, requests=0):
    return Counters(at, busy, total, mem, recv, sent, requests)


def _point(t, cpu=10.0, rps=1.0):
    return {"t": t, "cpu": cpu, "mem": 50.0, "net_in": 100.0, "net_out": 200.0, "rps": rps}


def _tier(name):
    return next(tier for tier in TIERS if tier.name == name)


class TestDomain(unittest.TestCase):
    def test_rates_between_two_readings(self):
        point = point_between(_counters(T0, 10, 100, recv=1000, sent=0, requests=5),
                              _counters(T0 + 10, 15, 120, mem=55.5, recv=3000, sent=500, requests=25))
        self.assertEqual({k: point[k] for k in ("t", "cpu", "mem", "net_in", "net_out", "rps")},
                         {"t": T0 + 10, "cpu": 25.0, "mem": 55.5, "net_in": 200.0, "net_out": 50.0, "rps": 2.0})
        self.assertEqual(set(point), {"t", "e5xx", *SERIES})  # e5xx : alertes seulement, jamais garde dans les anneaux
        self.assertIsNone(point["swap"])  # mesure absente : None, jamais 0
        self.assertIsNone(point_between(_counters(T0 + 10), _counters(T0 + 10)))  # meme instant
        rotated = point_between(_counters(T0, requests=50), _counters(T0 + 10, requests=3))
        self.assertIsNone(rotated["rps"])  # compteur reparti de zero : pas de valeur fausse
        self.assertIsNone(point_between(_counters(T0, requests=None), _counters(T0 + 10))["rps"])

    def test_new_measures_between_two_readings(self):
        before = Counters(T0, 0, 0, 40, 0, 0, 0, swap_percent=5.0, load=(0.5, 0.4, 0.3), site_recv=1000,
                          site_sent=5000, tcp=10, sockets=300, disk_read=0, disk_write=10_000, disk_used=61.0,
                          procs=250, serv_cpu=100.0, serv_mem=50_000_000, cpu_count=4, temp=48.0, battery=90.0)
        after = Counters(T0 + 10, 0, 0, 40, 0, 0, 0, swap_percent=6.0, load=(1.5, 0.6, 0.35), site_recv=2000,
                         site_sent=105_000, tcp=12, sockets=310, disk_read=40_960, disk_write=10_000, disk_used=61.5,
                         procs=251, serv_cpu=104.0, serv_mem=60_000_000, cpu_count=4, temp=52.5, battery=89.0)
        point = point_between(before, after)
        self.assertEqual({k: point[k] for k in ("swap", "load1", "load5", "load15", "site_in", "site_out", "tcp",
                                                "sockets", "disk_read", "disk_write", "disk_used", "procs",
                                                "serv_cpu", "serv_mem", "temp", "battery")},
                         {"swap": 6.0, "load1": 1.5, "load5": 0.6, "load15": 0.35, "site_in": 100.0,
                          "site_out": 10_000.0, "tcp": 12.0, "sockets": 310.0, "disk_read": 4096.0, "disk_write": 0.0,
                          "disk_used": 61.5, "procs": 251.0, "serv_cpu": 10.0, "serv_mem": 60_000_000.0,
                          "temp": 52.5, "battery": 89.0})  # serv_cpu : 4 s sur 10 s et 4 coeurs = 10 % de la machine
        restarted = Counters(T0 + 20, 0, 0, 40, 0, 0, 0, site_recv=10, serv_cpu=1.0)
        self.assertIsNone(point_between(after, restarted)["site_in"])  # serveur redemarre : pas de debit negatif

    def test_tiers_are_bounded_and_keep_average_and_worst_minute(self):
        rings = HistoryRings()
        for i in range(_tier("s10").size + 40):  # 400 releves de 10 s : 66 min 40
            minute = i // 6
            rings.add(_point(T0 + 10 * (i + 1), cpu=90.0 if minute == 2 else 10.0))
        self.assertEqual(len(rings.short), _tier("s10").size)
        minutes = rings.rings["m1"].points
        self.assertEqual([p["cpu"] for p in list(minutes)[:4]], [10.0, 10.0, 90.0, 10.0])
        five = rings.rings["m5"].points
        self.assertEqual(len(five), 13)  # 13 tranches de 5 min closes, la suivante en cours
        self.assertEqual((five[0]["t"], five[0]["cpu"], five[0]["cpu_max"]), (T0 + 300, 26.0, 90.0))
        rings.add(_point(T0))  # en arriere : ignore
        self.assertEqual(rings.short[-1]["t"], T0 + 10 * (_tier("s10").size + 40))

    def test_series_of_each_range_and_mode(self):
        rings = HistoryRings()
        for i in range(40):
            rings.add(_point(T0 + 10 * (i + 1), cpu=80.0 if i < 6 else 20.0))
        now = T0 + 400
        hour = rings.series("1h", now)
        self.assertEqual((hour["step"], len(hour["points"]), hour["now"] - hour["from"], hour["has_max"]),
                         (10, 40, 3600, False))
        three = rings.series("3h", now)
        self.assertEqual((three["step"], len(three["points"]), three["now"] - three["from"]), (60, 7, 3 * 3600))
        day = rings.series("24h", now)
        self.assertEqual((day["step"], day["now"] - day["from"], len(day["points"])), (300, 86400, 2))
        self.assertEqual(day["points"][0]["cpu"], 32.0)  # minutes 80, 20, 20, 20, 20
        self.assertEqual(rings.series("24h", now, "max")["points"][0]["cpu"], 80.0)
        self.assertEqual(rings.series("3h", now, "max")["points"], three["points"])  # minute : meme courbe
        for name, span in (("12h", 12 * 3600), ("7j", 7 * 86400), ("30j", 30 * 86400)):
            series = rings.series(name, now, "max")
            self.assertEqual(series["now"] - series["from"], span)
            self.assertTrue(series["points"])  # la tranche en cours compte deja
        self.assertIsNone(rings.series("1an", now))
        self.assertIsNone(rings.series("1h", now, "pire"))
        self.assertEqual(len(rings.series("1h", now + 3600)["points"]), 0)  # tout est sorti de la fenetre

    def test_saved_file_round_trip_ignores_invalid_and_old_points(self):
        rings = HistoryRings()
        for i in range(700):
            rings.add(_point(T0 + 10 * (i + 1)))
        data = json.loads(json.dumps(rings.to_dict()))
        now = T0 + 7000  # dernier releve : rien n'est encore sorti de sa fenetre
        reloaded = HistoryRings.from_dict(data, now)
        for name in ("s10", "m1", "m5"):
            self.assertEqual(list(reloaded.rings[name].points), list(rings.rings[name].points), name)
        self.assertEqual(reloaded.series("24h", now, "max"), rings.series("24h", now, "max"))
        broken = json.loads(json.dumps(data))
        broken["tiers"]["m1"]["points"]["cpu"].pop()  # colonne plus courte : palier ignore, les autres restent
        broken["tiers"]["s10"]["points"]["cpu"][0] = "abime"
        damaged = HistoryRings.from_dict(broken, now)
        self.assertEqual(len(damaged.rings["m1"].points), 0)
        self.assertEqual(len(damaged.short), len(rings.short) - 1)
        self.assertEqual(len(HistoryRings.from_dict(data, now + 90_000).short), 0)  # plus d'une heure
        self.assertEqual(len(HistoryRings.from_dict({"format": 99}, T0).short), 0)
        self.assertEqual(len(HistoryRings.from_dict("abime", T0).short), 0)

    def test_format_1_file_is_taken_over(self):
        old = {"format": 1, "short": [_point(T0 + 10 * (i + 1)) for i in range(30)],
               "long": [_point(T0 - 300 * i, cpu=33.0) for i in range(3, 0, -1)], "bucket": None, "pending": []}
        rings = HistoryRings.from_dict(old, T0 + 300)
        self.assertEqual(len(rings.short), 30)
        self.assertEqual(len(rings.rings["m1"].points), 4)  # minutes refaites depuis l'heure gardee
        self.assertEqual([p["cpu_max"] for p in rings.rings["m5"].points], [33.0, 33.0, 33.0])
        self.assertIsNone(rings.short[0]["swap"])


class TestProbe(unittest.TestCase):
    def test_cpu_temperature_prefers_the_processor_package(self):
        from types import SimpleNamespace as S
        sensors = {"acpitz": [S(label="", current=70.0)],
                   "coretemp": [S(label="Core 0", current=55.0), S(label="Package id 0", current=58.0)]}
        self.assertEqual(cpu_temperature(sensors), 58.0)
        self.assertEqual(cpu_temperature({"acpitz": [S(label="", current=41.0)]}), 41.0)
        self.assertIsNone(cpu_temperature({"nvme": [S(label="Composite", current=40.0)]}))

    def test_process_tree_never_counts_the_past_of_processes_found_at_start(self):
        import psutil

        tree = ProcessTreeCpu()
        me = psutil.Process()
        total, memory = tree.update([me])
        self.assertEqual(total, 0.0)  # le passe de ce processus ne gonfle pas le premier point
        self.assertGreater(memory, 0)
        sum(range(3_000_000))
        again, _memory = tree.update([me])
        self.assertGreaterEqual(again, 0.0)
        self.assertGreaterEqual(tree.update([])[0], again)  # un processus parti ne fait pas reculer le total

    def test_real_reading_on_this_machine(self):
        with tempfile.TemporaryDirectory() as name:
            probe = HistoryProbe(lambda: Path(name) / "access.log", instance_root=Path(name),
                                 server_pids=lambda: [os.getpid()])
            first, second = probe.read(), probe.read()
            capacities = probe.capacities()
        self.assertIsNotNone(second.disk_used)
        self.assertIsNotNone(second.procs)
        self.assertIsNotNone(second.serv_mem)
        self.assertGreaterEqual(second.serv_cpu, first.serv_cpu)
        self.assertGreaterEqual(second.cpu_count, 1)
        self.assertGreaterEqual(capacities["coeurs"], 1)
        self.assertGreater(capacities["memoire"], 0)
        self.assertGreater(capacities["disque"], 0)
        battery = capacities.get("batterie")
        self.assertTrue(battery is None or isinstance(battery["secteur"], bool))


class TestLineCounter(unittest.TestCase):
    def test_counts_new_lines_only_and_follows_rotation(self):
        with tempfile.TemporaryDirectory() as name:
            log = Path(name) / "access.log"
            log.write_text("ancienne\n" * 5)
            counter = LineCounter(lambda: log)
            self.assertEqual(counter.count(), 0)  # premier releve : la suite seulement
            with log.open("a") as handle:
                handle.write("a\nb\nc\n")
            self.assertEqual(counter.count(), 3)
            os.rename(log, Path(name) / "access.log.1")
            log.write_text("x\ny\n")
            self.assertEqual(counter.count(), 5)  # nouveau fichier : depuis son debut
            log.write_text("z\n")  # tronque
            self.assertEqual(counter.count(), 6)
            log.unlink()
            self.assertIsNone(counter.count())
        with tempfile.TemporaryDirectory() as name:  # journal absent au premier releve (instance neuve)
            log = Path(name) / "access.log"
            counter = LineCounter(lambda: log)
            self.assertIsNone(counter.count())
            log.write_text("a\nb\n")  # premieres visites : comptees, pas prises pour un point de depart
            self.assertEqual(counter.count(), 2)


class _Probe:
    def __init__(self):
        self.readings = [_counters(T0 + 10 * i, busy=5.0 * i, total=20.0 * i, requests=3 * i) for i in range(50)]

    def read(self):
        return self.readings.pop(0)

    def capacities(self):
        return {"memoire": 16 * 1024 ** 3, "coeurs": 8}


class _MemoryStore:
    def __init__(self, data=None, fail=False):
        self.data, self.fail, self.saves = data, fail, 0

    def load(self):
        return self.data

    def save(self, data):
        if self.fail:
            raise OSError("lecture seule")
        self.data, self.saves = data, self.saves + 1


class TestRecorder(unittest.TestCase):
    def test_records_saves_and_reloads(self):
        store = _MemoryStore()
        recorder = HistoryRecorder(_Probe(), store, clock=lambda: T0 + 200)
        probe = _Probe()
        for _ in range(5):
            recorder.record(probe.read())
        self.assertEqual(len(recorder.rings.short), 4)  # le premier releve sert de point de depart
        self.assertEqual(recorder.rings.short[-1]["cpu"], 25.0)
        self.assertEqual(recorder.rings.short[-1]["rps"], 0.3)
        recorder.save()
        again = HistoryRecorder(_Probe(), store, clock=lambda: T0 + 200)
        self.assertEqual(list(again.rings.short), list(recorder.rings.short))
        HistoryRecorder(_Probe(), _MemoryStore(fail=True)).save()  # dossier non inscriptible : pas d'exception

    def test_run_samples_then_saves_on_stop(self):
        store = _MemoryStore()
        recorder = HistoryRecorder(_Probe(), store, clock=lambda: T0 + 100, step=0.01)

        async def scenario():
            stop = asyncio.Event()
            task = asyncio.ensure_future(recorder.run(stop))
            await asyncio.sleep(0.15)
            stop.set()
            await task

        asyncio.run(scenario())
        self.assertGreater(len(recorder.rings.short), 2)
        self.assertGreaterEqual(store.saves, 1)


class TestWebView(unittest.TestCase):
    _request = _web.TestWebApp._request
    _login = _web.TestWebApp._login

    def setUp(self):
        self.store = _Store([AdminAccount("admin", hash_password("mot-de-passe-2"), "administration")])
        self.clock = _Clock()
        recorder = HistoryRecorder(_Probe(), _MemoryStore(), clock=lambda: T0 + 100)
        probe = _Probe()
        for _ in range(4):
            recorder.record(probe.read())
        settings = AdminWebSettings(allowed_networks=("127.0.0.0/8",))
        self.app = AdminWebApp(settings, _auth(self.store, self.clock), "prod", history=recorder)

    def test_history_page_and_api(self):
        token = self._login()
        home = self._request("GET", "/", cookie=token).body.decode()
        self.assertIn('href="/historique"', home)
        page = self._request("GET", "/historique", cookie=token)
        self.assertEqual(page.status, 200)
        self.assertIn(b'data-history="/api/historique"', page.body)
        self.assertEqual(page.body.count(b'<figure class="chart"'), 16)
        api = self._request("GET", "/api/historique?plage=1h", cookie=token)
        self.assertEqual(api.status, 200)
        payload = json.loads(api.body)
        self.assertEqual((payload["step"], len(payload["points"])), (10, 3))
        self.assertEqual(payload["capacites"], {"memoire": 16 * 1024 ** 3, "coeurs": 8})  # « utilise / total »
        self.assertEqual(page.body.count(b"data-detail="), 6)  # memoire, swap, disque, omega-serv x2, batterie
        for name in ("3h", "12h", "24h", "7j", "30j"):
            self.assertIn(f'data-range="{name}"'.encode(), page.body)
            self.assertEqual(self._request("GET", f"/api/historique?plage={name}&mode=max", cookie=token).status, 200)
        self.assertIn(b'data-mode="max"', page.body)
        self.assertEqual(self._request("GET", "/api/historique?plage=1an", cookie=token).status, 404)
        self.assertEqual(self._request("GET", "/api/historique?plage=1h&mode=pire", cookie=token).status, 404)
        self.assertEqual(self._request("GET", "/api/historique").status, 401)

    def test_history_disabled_hides_the_view(self):
        settings = AdminWebSettings(allowed_networks=("127.0.0.0/8",))
        self.app = AdminWebApp(settings, _auth(self.store, self.clock), "prod")
        token = self._login()
        self.assertNotIn(b'href="/historique"', self._request("GET", "/", cookie=token).body)
        self.assertEqual(self._request("GET", "/historique", cookie=token).status, 404)
        self.assertEqual(self._request("GET", "/api/historique", cookie=token).status, 404)


class TestSetting(unittest.TestCase):
    def test_history_setting_defaults_on_and_must_be_boolean(self):
        self.assertTrue(AdminWebSettings.from_settings({}).history)
        self.assertFalse(AdminWebSettings.from_settings({"history": False}).history)
        self.assertEqual(AdminWebSettings.from_settings({"history": False}).to_settings()["history"], False)
        errors = validate_admin_web(AdminWebSettings(history="oui"), server_bind="0.0.0.0", server_port=80)
        self.assertTrue(any("history" in error for error in errors))
        self.assertEqual(validate_admin_web(AdminWebSettings(), server_bind="0.0.0.0", server_port=80), [])



if __name__ == "__main__":
    unittest.main()
