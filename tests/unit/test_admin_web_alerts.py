# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Alertes locales du panneau web (etude modules, module 1 ; decisions de l'auteur du 2026-11-17 : locales
seulement, aucun envoi) : seuil, duree, retour a la normale, maintenance, paliers des certificats, sources completes,
journal, vue web."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from omega_serv.application.admin_web.alert_monitor import AlertMonitor
from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.application.tls.certificate_inventory import CertificateLine
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.alerts import AlertBook, Reading, thresholds_from_settings
from omega_serv.domain.admin_web.settings import AdminWebSettings, validate_admin_web
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.infrastructure.admin_web.alert_store import LOG_RELATIVE_PATH, AlertStore
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

DEFAULTS = thresholds_from_settings(None)


class TestBook(unittest.TestCase):
    def test_hold_then_open_then_hysteresis_close(self):
        book = AlertBook()
        self.assertEqual(book.evaluate([Reading("disque", 91)], DEFAULTS, 0), [])  # 5 min de maintien
        self.assertEqual(book.evaluate([Reading("disque", 92)], DEFAULTS, 200), [])
        (opened,) = book.evaluate([Reading("disque", 93)], DEFAULTS, 300)
        self.assertEqual((opened.kind, opened.alert.value, opened.alert.threshold), ("opened", 93, 90))
        self.assertEqual(book.evaluate([Reading("disque", 87)], DEFAULTS, 400), [])  # sous le seuil, pas encore 85
        self.assertEqual(book.active["disque"].worst, 93)
        (closed,) = book.evaluate([Reading("disque", 84)], DEFAULTS, 500)
        self.assertEqual((closed.kind, closed.alert.closed_at), ("closed", 500))
        self.assertEqual(len(book.history), 1)
        self.assertEqual(book.evaluate([Reading("disque", 99)], DEFAULTS, 501), [])  # nouvel episode : nouveau maintien
        self.assertEqual(book.evaluate([Reading("disque", None)], DEFAULTS, 900), [])  # pas de mesure : rien ne change

    def test_battery_is_low_side_and_maintenance_blocks_opening(self):
        book = AlertBook()
        book.evaluate([Reading("batterie", 10)], DEFAULTS, 0, maintenance=True)
        self.assertEqual(book.evaluate([Reading("batterie", 9)], DEFAULTS, 200, maintenance=True), [])
        (opened,) = book.evaluate([Reading("batterie", 8)], DEFAULTS, 300)
        self.assertEqual(opened.alert.rule, "batterie")
        (closed,) = book.evaluate([Reading("batterie", 21)], DEFAULTS, 400, maintenance=True)  # se ferme toujours
        self.assertEqual(closed.kind, "closed")

    def test_subjects_certificate_steps_and_complete_sources(self):
        book = AlertBook()
        events = book.evaluate([Reading("certificat", 25, "a.pem"), Reading("certificat", 200, "b.pem"),
                                Reading("incident", 1, "inc-1"), Reading("backend", 1, "web/b1")],
                               DEFAULTS, 0, complete_rules=frozenset({"certificat", "incident", "backend"}))
        self.assertEqual(sorted(e.alert.key for e in events), ["certificat:a.pem", "incident:inc-1"])
        self.assertEqual(book.active["certificat:a.pem"].level, "30")
        (worse,) = book.evaluate([Reading("certificat", 6, "a.pem")], DEFAULTS, 10)
        self.assertEqual((worse.kind, worse.alert.level), ("worse", "7"))
        (backend,) = book.evaluate([Reading("backend", 1, "web/b1")], DEFAULTS, 120)  # 2 min de maintien
        self.assertEqual(backend.alert.subject, "web/b1")
        closed = book.evaluate([Reading("backend", 0, "web/b1")], DEFAULTS, 200,
                               complete_rules=frozenset({"incident", "certificat"}))  # incident ferme, certificat parti
        self.assertEqual(sorted(e.alert.key for e in closed), ["backend:web/b1", "certificat:a.pem", "incident:inc-1"])
        self.assertEqual(book.active, {})
        again = AlertBook.from_dict(book.to_dict())
        self.assertEqual(again.history, book.history)

    def test_settings_thresholds_and_disabled_rules(self):
        thresholds = thresholds_from_settings({"disque": 80, "memoire": False, "swap": 500})
        self.assertEqual((thresholds["disque"], thresholds["memoire"], thresholds["swap"]), (80.0, None, 80.0))
        book = AlertBook()
        book.evaluate([Reading("memoire", 99)], DEFAULTS, 0)
        book.evaluate([Reading("memoire", 99)], DEFAULTS, 600)
        self.assertIn("memoire", book.active)
        (closed,) = book.evaluate([Reading("memoire", 99)], thresholds, 700)  # regle coupee : alerte fermee
        self.assertEqual(closed.kind, "closed")
        errors = validate_admin_web(AdminWebSettings(alerts={"disque": 120, "inconnue": 3}), server_bind="0.0.0.0",
                                    server_port=8080)
        self.assertEqual(len([e for e in errors if "alerts" in e]), 2)
        self.assertEqual(validate_admin_web(AdminWebSettings(alerts={"disque": 80, "swap": False}),
                                            server_bind="0.0.0.0", server_port=8080), [])


class TestMonitorAndView(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.now = [1_700_000_000.0]
        self.store = AlertStore(LocalFilesystem(), self.root)
        self.monitor = AlertMonitor(self.store, lambda: DEFAULTS, clock=lambda: self.now[0])

    def test_points_and_sources_write_the_log_and_survive_a_restart(self):
        self.monitor.on_point({"disk_used": 95.0, "mem": 20.0})
        self.now[0] += 301
        self.monitor.on_point({"disk_used": 96.0, "mem": 20.0})
        self.monitor.on_sources([("web/b1", "up")], ["inc-7"], [CertificateLine("Site", "s.pem", "urgent", 3)])
        log = (self.root / LOG_RELATIVE_PATH).read_text()
        self.assertIn("ouverte disque valeur=96 seuil=90", log)
        self.assertIn("ouverte incident sujet=inc-7", log)
        self.assertIn("ouverte certificat sujet=s.pem valeur=3 seuil=30 palier=7", log)
        again = AlertMonitor(self.store, lambda: DEFAULTS, clock=lambda: self.now[0])
        self.assertEqual(set(again.book.active), {"disque", "incident:inc-7", "certificat:s.pem"})
        self.store.set_maintenance(self.now[0] + 3600)
        self.assertIsNotNone(again.maintenance_until)
        self.store.set_maintenance(None)
        self.assertIsNone(again.maintenance_until)

    def test_web_view_lists_current_and_past_alerts(self):
        self.monitor.on_sources(None, ["inc-7"], None)
        self.now[0] += 10
        self.monitor.on_sources(None, [], None)  # incident ferme
        self.monitor.on_sources(None, ["inc-8"], None)
        accounts = (AdminAccount("lecteur", hash_password("mot-de-passe-1"), "lecture"),)
        auth = AdminAuth(lambda: accounts, lambda: 1.7e9, lambda line: None, local_only=True,
                         used_backup_codes=set, mark_backup_code_used=lambda code: None)
        app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",)), auth, "prod", alerts=self.monitor)

        def request(method, target, body=b"", cookie=""):
            headers = (("Host", "127.0.0.1:9643"), ("Cookie", cookie))
            return asyncio.run(app.handle(AdminRequest("127.0.0.1", method, target, headers, body)))
        body = urlencode({"identifiant": "lecteur", "mot_de_passe": "mot-de-passe-1"}).encode()
        token = dict(request("POST", "/connexion", body).headers)["Set-Cookie"].split(";")[0].split("=", 1)[1]
        page = request("GET", "/alertes", cookie=f"{COOKIE_NAME}={token}").body.decode()
        self.assertIn("Alertes (1)", page)  # compte dans la barre des vues
        self.assertIn("inc-8", page)
        self.assertIn("inc-7", page)  # historique
        self.assertIn("Historique désactivé", page)


if __name__ == "__main__":
    unittest.main()
