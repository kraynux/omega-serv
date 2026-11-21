# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tableau de bord web, lot 2 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §2) : processus d'administration lance
par `serve`, de bout en bout (vrai serveur, deux moteurs) :

- ecoute sur son propre port ; sans session, renvoi vers la page de connexion ; en-tetes de securite ;
- adresse hors des reseaux permis -> 403 ; methode inconnue -> 405 ;
- lot 3 : vrai compte (fichier secure/auth/admin-web.json), connexion, cookie, journal d'audit ; compte
  d'administration sans TOTP sur une ecoute hors de la machine -> l'administration ne demarre pas (choix b) ;
- TLS par certificat dedie ;
- certificat absent : le site demarre quand meme, l'administration reste arretee et le dit dans error.log ;
- arretee avec le serveur (aucun processus orphelin, port libere).

Le binaire natif n'est pas versionne : sans build, la moitie native est sautee."""
from __future__ import annotations

import http.client
import json
import re
import socket
import ssl
import subprocess
import time
import unittest

from omega_serv.domain.security.auth.password_hashing import hash_password
from tests.integration.proxy_harness import BANNED_IP, NATIVE_BINARY, ProxyProject


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _wait_log(path, text: str, timeout: float = 20.0) -> str:
    """Le processus d'administration ecrit sa ligne apres son propre demarrage (plus lent sur une machine chargee) :
    on attend la ligne, jamais un delai fixe."""
    deadline = time.monotonic() + timeout
    content = ""
    while time.monotonic() < deadline:
        content = path.read_text() if path.exists() else ""
        if text in content:
            break
        time.sleep(0.2)
    return content


def _wait_port(port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _run_state(project, until, timeout: float = 20.0) -> dict:
    """Lot 8 : var/run/admin/etat.json ecrit par le processus d'administration (lu par Configuration distante)."""
    path = project.root / "var" / "run" / "admin" / "etat.json"
    deadline = time.monotonic() + timeout
    data: dict = {}
    while time.monotonic() < deadline:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        if data and until(data):
            return data
        time.sleep(0.1)
    return data


class _AdminWebCase:
    engine = "python"

    def _project(self, admin: dict) -> tuple[ProxyProject, int]:
        port = _free_port()
        project = ProxyProject(self.engine, _free_port(), proxy={"engine": "native"} if self.engine == "native" else None,
                               options={"admin_web": {"enabled": True, "bind": "127.0.0.1", "port": port, **admin}})
        self.addCleanup(project.stop)
        return project, port

    def _get(self, port: int, method: str = "GET", tls: bool = False, path: str = "/", body: str | None = None,
             headers: dict | None = None) -> http.client.HTTPResponse:
        if tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            connection: http.client.HTTPConnection = http.client.HTTPSConnection("127.0.0.1", port, timeout=10,
                                                                                  context=context)
        else:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        self.addCleanup(connection.close)
        connection.request(method, path, body=body, headers=headers or {})
        return connection.getresponse()

    def test_own_port_login_redirect_and_security_headers(self):
        project, port = self._project({"tls": "none"})
        project.start()
        self.assertEqual(project.effective_engine(), self.engine)
        self.assertTrue(_wait_port(port))
        response = self._get(port)
        response.read()
        self.assertEqual((response.status, response.getheader("Location")), (303, "/connexion"))
        login = self._get(port, path="/connexion")
        body = login.read().decode()
        self.assertEqual(login.status, 200)
        self.assertIn('name="identifiant"', body)
        self.assertIn("default-src 'none'", login.getheader("Content-Security-Policy"))
        self.assertEqual(login.getheader("X-Frame-Options"), "DENY")
        self.assertEqual(login.getheader("Cache-Control"), "no-store")
        self.assertIsNone(login.getheader("Strict-Transport-Security"))  # pas de TLS
        self.assertEqual(self._get(port, "DELETE").status, 405)
        self.assertEqual(project.request("GET", "/")[0], 200)  # le site, lui, sert normalement
        state = _run_state(project, lambda d: d.get("listening"))
        self.assertEqual((state["listening"], state["port"], state["problem"]), (True, port, ""))
        project.stop()
        self.assertFalse(_wait_port(port, timeout=1.0))  # arretee avec le serveur

    def test_real_account_login_and_audit(self):
        project, port = self._project({"tls": "none"})
        auth = project.root / "secure" / "auth"
        auth.mkdir(parents=True)
        (auth / "admin-web.json").write_text(json.dumps({"version": 1, "accounts": [
            {"username": "admin", "password_hash": hash_password("mot-de-passe-2"), "role": "administration"}]}))
        project.start()
        self.assertTrue(_wait_port(port))
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        refused = self._get(port, "POST", path="/connexion", body="identifiant=admin&mot_de_passe=faux", headers=form)
        refused.read()
        self.assertEqual(refused.status, 401)
        accepted = self._get(port, "POST", path="/connexion", headers=form,
                             body="identifiant=admin&mot_de_passe=mot-de-passe-2&mode=administration")
        accepted.read()
        self.assertEqual(accepted.status, 303)
        cookie = accepted.getheader("Set-Cookie").split(";")[0]
        home = self._get(port, headers={"Cookie": cookie})
        self.assertIn("Administration", home.read().decode())
        audit = (project.root / "var" / "log" / "admin-audit.log").read_text()
        self.assertIn("echec de connexion compte='admin'", audit)
        self.assertIn("connexion compte=admin role=administration mode=administration", audit)

    def _logged_in(self, project: ProxyProject, port: int, role: str = "administration") -> str:
        auth = project.root / "secure" / "auth"
        auth.mkdir(parents=True, exist_ok=True)
        (auth / "admin-web.json").write_text(json.dumps({"version": 1, "accounts": [
            {"username": "admin", "password_hash": hash_password("mot-de-passe-2"), "role": role}]}))
        project.start()
        self.assertTrue(_wait_port(port))
        response = self._get(port, "POST", path="/connexion", body="identifiant=admin&mot_de_passe=mot-de-passe-2",
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
        response.read()
        return response.getheader("Set-Cookie").split(";")[0]

    def _json(self, port: int, path: str, cookie: str, until=None, timeout: float = 20.0) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            response = self._get(port, path=path, headers={"Cookie": cookie})
            payload = json.loads(response.read())
            if until is None or until(payload) or time.monotonic() > deadline:
                return payload
            time.sleep(0.5)

    def test_dashboard_panels_logs_and_audit_over_the_api(self):
        project, port = self._project({"tls": "none"})
        cookie = self._logged_in(project, port)
        for _ in range(3):
            project.request("GET", "/")
        self.assertEqual(json.loads(self._get(port, path="/api/vue/etat").read())["error"], "session")
        state = self._json(port, "/api/vue/etat", cookie, until=lambda p: p.get("sections"))
        titles = [section["title"] for section in state["sections"]]
        self.assertIn("MOTEUR HTTP", titles)
        self.assertEqual(state["sections"][0]["rows"][0]["label"], "Type d'instance")
        flux = self._json(port, "/api/vue/flux", cookie, until=lambda p: p.get("sections"))
        backends = next(s for s in flux["sections"] if s["title"] == "BACKENDS")  # instance mixte (zone /api/)
        self.assertEqual(backends["note"], "")  # mesures lues dans le serveur en marche, jamais « serveur arrete »
        self.assertEqual(len(backends["table"]), 1)
        resources = self._json(port, "/api/vue/ressources", cookie, until=lambda p: p.get("sections"))
        machine = next(s for s in resources["sections"] if s["title"] == "MACHINE")
        self.assertIsNotNone(machine["rows"][0]["gauge"])
        self.assertTrue(self._json(port, "/api/vue/securite", cookie, until=lambda p: p.get("sections"))["sections"])
        page = self._get(port, headers={"Cookie": cookie}).read().decode()
        self.assertIn('data-api="/api/vue/flux"', page)
        self.assertIn('src="/static/admin.js"', page)
        self.assertEqual(self._get(port, path="/static/admin.js").status, 200)

        library = self._json(port, "/api/journaux", cookie)["logs"]
        self.assertEqual([log["label"] for log in library][:2], ["access.log (cette instance)",
                                                                 "error.log (cette instance)"])
        if library:
            first = library[0]["id"]
            snapshot = self._json(port, f"/api/journal?id={first}&lignes=5", cookie)
            self.assertLessEqual(len(snapshot["lines"]), 5)
            follow = self._json(port, f"/api/journal/suite?id={first}&curseur={snapshot['cursor']}", cookie)
            self.assertGreaterEqual(follow["cursor"], snapshot["cursor"])
        self.assertEqual(self._get(port, path="/api/journal?id=inconnu", headers={"Cookie": cookie}).status, 404)
        audit = self._json(port, "/api/audit", cookie)
        self.assertTrue(any("connexion compte=admin" in line for line in audit["lines"]))

    def test_security_page_lists_the_blocklist(self):
        port = _free_port()
        project = ProxyProject(self.engine, _free_port(), proxy={"engine": "native"} if self.engine == "native" else None,
                               options={"waf": {"enabled": True},
                                        "admin_web": {"enabled": True, "bind": "127.0.0.1", "port": port, "tls": "none"}})
        self.addCleanup(project.stop)
        cookie = self._logged_in(project, port)
        security = self._json(port, "/api/vue/securite", cookie, until=lambda p: p.get("sections"))
        bans = next(s for s in security["sections"] if s["title"] == "BANS")
        self.assertIn(BANNED_IP, [row[0] for row in bans["table"]])

    def test_read_only_account_has_no_audit(self):
        project, port = self._project({"tls": "none"})
        cookie = self._logged_in(project, port, role="lecture")
        self.assertEqual(self._get(port, path="/api/audit", headers={"Cookie": cookie}).status, 403)
        self.assertEqual(self._get(port, path="/audit", headers={"Cookie": cookie}).status, 403)
        self.assertNotIn("/audit", self._get(port, headers={"Cookie": cookie}).read().decode())

    def test_admin_account_without_totp_blocks_remote_listening(self):
        project, port = self._project({"tls": "own", "bind": "0.0.0.0"})
        certs = project.root / "secure" / "certificates" / "admin"
        certs.mkdir(parents=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-keyout", str(certs / "admin.key"), "-out", str(certs / "admin.pem"), "-days", "2",
                        "-subj", "/CN=localhost"], check=True, capture_output=True)
        auth = project.root / "secure" / "auth"
        auth.mkdir(parents=True)
        (auth / "admin-web.json").write_text(json.dumps({"version": 1, "accounts": [
            {"username": "admin", "password_hash": hash_password("mot-de-passe-2"), "role": "administration"}]}))
        project.start()
        self.assertEqual(project.request("GET", "/")[0], 200)  # le site demarre quand meme
        self.assertIn("TOTP obligatoire", _wait_log(project.root / "var" / "log" / "error.log", "TOTP obligatoire"))
        self.assertFalse(_wait_port(port, timeout=1.0))

    def test_address_outside_allowed_networks_is_refused(self):
        project, port = self._project({"tls": "none", "allowed_networks": ["10.0.0.0/8"]})
        project.start()
        self.assertTrue(_wait_port(port))
        self.assertEqual(self._get(port, path="/connexion").status, 403)

    def test_own_certificate_serves_https(self):
        project, port = self._project({"tls": "own"})
        certs = project.root / "secure" / "certificates" / "admin"
        certs.mkdir(parents=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-keyout", str(certs / "admin.key"), "-out", str(certs / "admin.pem"), "-days", "2",
                        "-subj", "/CN=localhost"], check=True, capture_output=True)
        project.start()
        self.assertTrue(_wait_port(port))
        response = self._get(port, tls=True, path="/connexion")
        response.read()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Strict-Transport-Security"), "max-age=31536000")

    def test_missing_certificate_never_stops_the_site(self):
        project, port = self._project({"tls": "own"})  # aucun certificat cree
        project.start()
        self.assertEqual(project.request("GET", "/")[0], 200)
        error_log = _wait_log(project.root / "var" / "log" / "error.log", "administration web : certificat illisible")
        self.assertIn("administration web : certificat illisible", error_log)
        self.assertFalse(_wait_port(port, timeout=1.0))
        state = _run_state(project, lambda d: d.get("problem"))
        self.assertEqual((state["listening"], state["problem"]), (False, "certificate"))

    def test_port_taken_by_another_program_is_reported(self):
        """Lot 8 : essai reel du 2026-11-17 (KULA sur 8443) : le site demarre, l'etat dit « ecoute impossible »."""
        project, port = self._project({"tls": "none"})
        with socket.socket() as other_program:
            other_program.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            other_program.bind(("127.0.0.1", port))
            other_program.listen(1)
            project.start()
            self.assertEqual(project.request("GET", "/")[0], 200)
            state = _run_state(project, lambda d: d.get("problem"))
        self.assertEqual((state["listening"], state["problem"], state["port"]), (False, "listen", port))


    def test_site_traffic_reaches_the_history(self):
        """Lot 9b (plan §9.5) : octets des visiteurs comptes par le moteur (Python, ou natif dans sa trame HEALTH),
        publies sous var/run/traffic/<pid>.json, additionnes par le processus d'administration et traces dans
        l'historique (Telechargements / Televersement). Envoi d'un corps : le televersement aussi."""
        project, port = self._project({"tls": "none"})
        cookie = self._logged_in(project, port)
        traffic = project.root / "var" / "run" / "traffic"
        point: dict = {}
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            project.request("GET", "/")
            project.request("POST", "/", body=b"x" * 4096)
            series = self._json(port, "/api/historique?plage=1h", cookie)
            point = series["points"][-1] if series["points"] else {}
            if (point.get("site_out") or 0) > 0 and (point.get("site_in") or 0) > 4096 / 10:
                break
            time.sleep(1)
        files = list(traffic.glob("*.json"))
        self.assertTrue(files)
        self.assertTrue(all(json.loads(f.read_text())["envoye"] > 0 for f in files))
        if self.engine == "native":  # le natif publie lui-meme (sous son PID), pas seulement le Python qui l'aide
            native_pid = json.loads((project.root / "var" / "run" / "engine-state.json").read_text())["native_pid"]
            self.assertIn(f"{native_pid}.json", [f.name for f in files])
        self.assertGreater(point.get("site_out") or 0, 0)
        self.assertGreater(point.get("site_in") or 0, 4096 / 10)  # au moins un corps par releve de 10 s
        project.process.terminate()
        project.process.wait(15)
        self.assertEqual([f for f in traffic.glob("*.json") if f.exists()], [])  # retires a l'arret


class TestPythonEngine(_AdminWebCase, unittest.TestCase):
    engine = "python"

    def test_history_records_every_10_seconds_and_is_saved_at_stop(self):
        """Lots 7 et 9 : le releve tourne meme sans page ouverte ; requetes comptees dans le journal d'acces ; fichier
        var/run/admin/history.json ecrit a l'arret (seulement le moteur Python : l'historique ne depend pas du moteur)."""
        project, port = self._project({"tls": "none"})
        cookie = self._logged_in(project, port)
        page = self._get(port, path="/historique", headers={"Cookie": cookie}).read().decode()
        self.assertIn('data-history="/api/historique"', page)
        for _ in range(20):
            project.request("GET", "/")
        series = self._json(port, "/api/historique?plage=1h", cookie, until=lambda p: len(p.get("points", [])) >= 2,
                            timeout=40)
        self.assertGreaterEqual(len(series["points"]), 2)
        point = series["points"][-1]
        self.assertTrue(0 <= point["cpu"] <= 100 and 0 < point["mem"] <= 100)
        self.assertIsNotNone(point["rps"])
        # Lot 9 : mesures de la machine et d'omega-serv relevees par le vrai processus d'administration
        self.assertIsNotNone(point["procs"])
        self.assertIsNotNone(point["disk_used"])
        self.assertIsNotNone(point["serv_mem"])
        self.assertEqual(self._json(port, "/api/historique?plage=24h", cookie)["step"], 300)
        self.assertEqual(self._json(port, "/api/historique?plage=30j&mode=max", cookie)["step"], 7200)
        # Etude modules du panneau web (2026-11-17) : trafic lu dans la meme passe, certificats, alertes, sessions
        traffic, deadline = "", time.monotonic() + 40
        while time.monotonic() < deadline:  # journal ecrit puis lu par le releve suivant (10 s)
            traffic = self._get(port, path="/trafic", headers={"Cookie": cookie}).read().decode()
            if re.search(r"<td>/</td><td>\d+</td>", traffic):
                break
            time.sleep(1)
        self.assertRegex(traffic, r"<td>/</td><td>\d+</td>")  # les 20 requetes vers / comptees
        for path, marker in (("/certificats", "Certificats"), ("/alertes", "Aucune alerte en cours."),
                             ("/sessions", "(cette session)")):
            self.assertIn(marker, self._get(port, path=path, headers={"Cookie": cookie}).read().decode(), path)
        published = project.root / "var" / "run" / "admin" / "sessions.json"
        deadline = time.monotonic() + 15
        while not published.exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertNotIn(cookie.split("=", 1)[1], published.read_text())  # liste pour la TUI, jamais le jeton
        project.process.terminate()  # pas project.stop() : il efface aussi le dossier du projet
        project.process.wait(15)
        self.assertTrue(list((project.root / "var" / "lib" / "admin" / "stats").glob("*.json")))  # jour ecrit a l'arret
        saved = json.loads((project.root / "var" / "run" / "admin" / "history.json").read_text())
        self.assertEqual(saved["format"], 2)
        self.assertGreaterEqual(len(saved["tiers"]["s10"]["points"]["t"]), 2)

    def test_history_can_be_turned_off(self):
        project, port = self._project({"tls": "none", "history": False})
        cookie = self._logged_in(project, port)
        self.assertNotIn('href="/historique"', self._get(port, headers={"Cookie": cookie}).read().decode())
        self.assertEqual(self._get(port, path="/api/historique", headers={"Cookie": cookie}).status, 404)
        project.process.terminate()
        project.process.wait(15)
        self.assertFalse((project.root / "var" / "run" / "admin" / "history.json").exists())


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeEngine(_AdminWebCase, unittest.TestCase):
    engine = "native"


if __name__ == "__main__":
    unittest.main()
