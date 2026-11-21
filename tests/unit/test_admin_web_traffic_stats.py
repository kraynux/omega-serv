# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Statistiques de trafic du panneau web (etude modules, module 2 ; decisions de l'auteur du 2026-11-17 : sans
pays, 5xx comptes dans la meme lecture du journal) : lignes du format combined, plafonds, jours, IP masquees, lignes
coupees entre deux lectures, taux de 5xx pour les alertes, vue Trafic."""
from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode

from omega_serv.application.admin_web.alert_monitor import AlertMonitor
from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.stats_aggregator import StatsAggregator
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.domain.admin_web import traffic_stats
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.alerts import thresholds_from_settings
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.admin_web.traffic_stats import StatsDay, agent_family, mask_ip, summarize
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.infrastructure.admin_web.alert_store import AlertStore
from omega_serv.infrastructure.admin_web.history_probe import LineCounter
from omega_serv.infrastructure.admin_web.stats_store import StatsStore
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

CHROME = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def line(ip="203.0.113.7", path="/index.html?x=1", status=200, size=512, referrer="https://ex.org/page",
         agent=CHROME) -> bytes:
    return (f'{ip} - - [17/Nov/2026:18:00:00 +0100] "GET {path} HTTP/1.1" {status} {size} "{referrer}" "{agent}" '
            f'req-1').encode()


class TestDay(unittest.TestCase):
    def test_lines_tables_and_families(self):
        day = StatsDay("2026-11-17")
        self.assertEqual(day.add(line(), 18), 200)
        day.add(line(path="/manque", status=404, referrer="-", agent="Googlebot/2.1 (+http://www.google.com/bot.html)"), 18)
        day.add(line(ip="2001:db8:1:2::5", status=503, size=0, agent="-"), 3)
        self.assertIsNone(day.add(b"pas une ligne du journal", 3))
        self.assertEqual((day.lines, day.requests, day.sent_bytes), (4, 3, 1024))
        self.assertEqual(day.statuses, {"200": 1, "404": 1, "503": 1})
        self.assertEqual((day.hours[18], day.hours[3]), (2, 1))
        self.assertEqual(day.tables["pages"], {"/index.html": 2, "/manque": 1})  # sans la query
        self.assertEqual(day.tables["not_found"], {"/manque": 1})
        self.assertEqual(day.tables["referrers"], {"ex.org": 2})
        self.assertEqual(day.tables["agents"], {"Chrome": 1, "robot : Googlebot": 1, "autre": 1})
        again = StatsDay.from_dict(day.to_dict(), "2026-11-17")
        self.assertEqual(again.to_dict(), day.to_dict())
        summary = summarize([day, again])
        self.assertEqual((summary.requests, summary.errors_4xx, summary.errors_5xx), (6, 2, 2))
        self.assertEqual(summary.tops["pages"][0], ("/index.html", 4))

    def test_cap_masks_and_families(self):
        original = traffic_stats.MAX_KEYS
        traffic_stats.MAX_KEYS = 3
        try:
            day = StatsDay("2026-11-17")
            for index in range(6):
                day.add(line(ip=f"198.51.100.{index}"), 0)
        finally:
            traffic_stats.MAX_KEYS = original
        self.assertEqual(len(day.tables["ips"]), 4)
        self.assertEqual(day.tables["ips"]["(autres)"], 3)
        self.assertEqual((mask_ip("203.0.113.77"), mask_ip("2001:db8:1:2::5")), ("203.0.113.0", "2001:db8:1::"))
        self.assertEqual(agent_family("curl/8.4.0"), "robot : curl")
        self.assertEqual(agent_family("Mozilla/5.0 Firefox/131.0"), "Firefox")


class TestAggregatorAndReader(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.now = [time.mktime((2026, 11, 17, 23, 59, 0, 0, 0, -1))]
        self.stats = StatsAggregator(StatsStore(LocalFilesystem(), self.root), clock=lambda: self.now[0])

    def test_reader_splits_lines_across_reads_and_days_roll(self):
        log = self.root / "access.log"
        log.write_bytes(b"ancienne ligne\n")
        counter = LineCounter(lambda: log, self.stats.feed)
        counter.count()  # premier releve : seulement la suite
        whole = line(status=500)
        with log.open("ab") as handle:
            handle.write(line() + b"\n" + whole[:20])
        counter.count()
        with log.open("ab") as handle:
            handle.write(whole[20:] + b"\n")
        self.assertEqual(counter.count(), 2)
        self.assertEqual(self.stats.errors_5xx, 1)  # ligne coupee entre deux lectures : comptee une fois, entiere
        self.now[0] += 120  # minuit passe : nouveau jour, l'ancien est ecrit
        self.stats.feed([line()])
        self.assertEqual(StatsStore(LocalFilesystem(), self.root).days(), ["2026-11-17"])
        self.assertEqual(self.stats.summary("jour").requests, 1)
        self.assertEqual(self.stats.summary("7j").requests, 3)

    def test_errors_rate_feeds_the_5xx_alert(self):
        monitor = AlertMonitor(AlertStore(LocalFilesystem(), self.root), lambda: thresholds_from_settings(None))
        for second in range(0, 300, 10):
            monitor.on_point({"t": 1000 + second, "rps": 2.0, "e5xx": 0.2})  # 10 % d'erreurs, 600 requetes
        self.assertIn("erreurs_5xx", monitor.book.active)
        quiet = AlertMonitor(AlertStore(LocalFilesystem(), self.root / "b"), lambda: thresholds_from_settings(None))
        quiet.on_point({"t": 1000, "rps": 0.2, "e5xx": 0.1})  # 2 requetes : jamais d'alerte
        self.assertNotIn("erreurs_5xx", quiet.book.active)


class TestView(unittest.TestCase):
    def test_traffic_view_with_masked_ips(self):
        with tempfile.TemporaryDirectory() as name:
            stats = StatsAggregator(StatsStore(LocalFilesystem(), Path(name)))
            stats.feed([line(ip="203.0.113.7"), line(ip="203.0.113.9", path="/x", status=404)])
            accounts = (AdminAccount("lecteur", hash_password("mot-de-passe-1"), "lecture"),)
            auth = AdminAuth(lambda: accounts, lambda: 1.7e9, lambda entry: None, local_only=True,
                             used_backup_codes=set, mark_backup_code_used=lambda code: None)
            app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",), stats_mask_ip=True), auth, "prod",
                              stats=stats)

            def request(method, target, body=b"", cookie=""):
                headers = (("Host", "127.0.0.1:9643"), ("Cookie", cookie))
                return asyncio.run(app.handle(AdminRequest("127.0.0.1", method, target, headers, body)))
            body = urlencode({"identifiant": "lecteur", "mot_de_passe": "mot-de-passe-1"}).encode()
            token = dict(request("POST", "/connexion", body).headers)["Set-Cookie"].split(";")[0].split("=", 1)[1]
            page = request("GET", "/trafic?periode=7j", cookie=f"{COOKIE_NAME}={token}").body.decode()
            self.assertIn('href="/trafic"', page)
            self.assertIn("203.0.113.0</td><td>2", page)  # deux adresses masquees en une ligne
            self.assertNotIn("203.0.113.7", page)
            self.assertIn("/x", page)
            self.assertIn('class="range active" href="/trafic?periode=7j"', page)
            self.assertEqual(request("GET", "/trafic").status, 303)


if __name__ == "__main__":
    unittest.main()
