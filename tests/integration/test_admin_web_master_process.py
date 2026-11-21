# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tableau de bord web, lot 6 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §7) : instance maitre de bout en bout,
deux vrais serveurs sur cette machine.

- l'instance suivie a son administration en HTTPS (certificat dedie auto-signe) ; elle ouvre une fenetre
  d'appairage par la CLI (`admin-web master pairing-code`) ;
- le maitre la relie depuis sa page Instances avec le code : empreinte du certificat epinglee ;
- page Instances, vue distante, ban pose a distance (blocklist reelle de l'instance suivie), double audit ;
- revocation sur l'instance suivie : le maitre voit « jeton refuse » ;
- chemin omega-connect : `admin-web master accept` sur l'instance, `admin-web instances add` sur le maitre (jeton
  lu sur l'entree standard), droits de lecture seulement ;
- « Relier au maître » de l'ecran Instances (2026-11-16) : le cas d'usage lance les vraies commandes des deux
  instances ; relier de nouveau (autres droits) remplace la liaison sans doublon.

Le binaire natif n'est pas versionne : sans build, la moitie native est sautee."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import ssl
import subprocess
import sys
import time
import unittest
from urllib.parse import urlencode

from omega_serv.application.admin_web.local_link import LocalLinkRequest, link_local_master
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.ports.instance_command_port import CommandReply
from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject
from tests.integration.test_admin_web_process import _free_port, _wait_port


def _accounts(project: ProxyProject) -> None:
    auth = project.root / "secure" / "auth"
    auth.mkdir(parents=True, exist_ok=True)
    (auth / "admin-web.json").write_text(json.dumps({"version": 1, "accounts": [
        {"username": "admin", "password_hash": hash_password("mot-de-passe-2"), "role": "administration"}]}))


def _cli(project: ProxyProject, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(project.root / "src")}
    return subprocess.run([sys.executable, "-m", "omega_serv", "--config", "config/omega-serve.json", "admin-web",
                           *args], cwd=project.root, env=env, input=stdin, capture_output=True, text=True,
                          timeout=60, check=False)


class _ProjectCommands:
    """Comme le lanceur de production, mais avec le code de chaque projet de test (pas d'environnement virtuel)."""

    def __init__(self, *projects: ProxyProject) -> None:
        self._projects = {project.root: project for project in projects}

    def run(self, root, arguments, stdin=""):
        done = _cli(self._projects[root], *tuple(arguments)[1:], stdin=stdin)
        return CommandReply(done.returncode, done.stdout, done.stderr)


class _Case:
    engine = "python"

    def setUp(self):
        self.follower_admin = _free_port()
        self.follower = ProxyProject(
            self.engine, _free_port(), proxy={"engine": "native"} if self.engine == "native" else None,
            options={"waf": {"enabled": True},
                     "admin_web": {"enabled": True, "bind": "127.0.0.1", "port": self.follower_admin, "tls": "own"}})
        self.addCleanup(self.follower.stop)
        certs = self.follower.root / "secure" / "certificates" / "admin"
        certs.mkdir(parents=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-keyout", str(certs / "admin.key"), "-out", str(certs / "admin.pem"), "-days", "2",
                        "-subj", "/CN=localhost"], check=True, capture_output=True)
        der = ssl.PEM_cert_to_DER_cert((certs / "admin.pem").read_text())
        self.fingerprint = hashlib.sha256(der).hexdigest()
        _accounts(self.follower)
        self.master_admin = _free_port()
        self.master = ProxyProject("python", _free_port(), options={
            "admin_web": {"enabled": True, "bind": "127.0.0.1", "port": self.master_admin, "tls": "none"}})
        self.addCleanup(self.master.stop)
        _accounts(self.master)
        self.follower.start()
        self.master.start()
        self.assertTrue(_wait_port(self.follower_admin))
        self.assertTrue(_wait_port(self.master_admin))
        status, headers, _body = self._call("POST", "/connexion", {
            "identifiant": "admin", "mot_de_passe": "mot-de-passe-2", "mode": "administration"})
        self.assertEqual(status, 303)
        self.cookie = headers["set-cookie"].split(";")[0]

    def _call(self, method: str, path: str, form: dict | None = None) -> tuple[int, dict[str, str], str]:
        connection = http.client.HTTPConnection("127.0.0.1", self.master_admin, timeout=20)
        try:
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if getattr(self, "cookie", None):
                headers["Cookie"] = self.cookie
            connection.request(method, path, body=urlencode(form).encode() if form is not None else None,
                               headers=headers)
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read().decode()
        finally:
            connection.close()

    def _csrf(self) -> str:
        return re.search(r'name="csrf" value="([^"]+)"', self._call("GET", "/instances")[2]).group(1)

    def _rows(self, until, timeout: float = 20.0) -> list[dict]:
        deadline = time.monotonic() + timeout
        rows: list[dict] = []
        while time.monotonic() < deadline:
            status, _headers, body = self._call("GET", "/api/instances")
            self.assertEqual(status, 200)
            rows = json.loads(body)["rows"]
            if until(rows):
                return rows
            time.sleep(0.5)
        self.fail(f"etat attendu jamais atteint : {rows}")

    def _blocklist(self) -> list[str]:
        path = self.follower.root / "var" / "lib" / "waf" / "blocklist.json"
        return [entry["network"] for entry in json.loads(path.read_text())["entries"]]

    def test_pairing_remote_view_remote_ban_revocation_and_connect_path(self):
        shown = _cli(self.follower, "master", "pairing-code", "--rights", "administration")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        code = re.search(r"\b[A-Z2-9]{4}-[A-Z2-9]{4}\b", shown.stdout).group(0)
        csrf = self._csrf()
        status, headers, _body = self._call("POST", "/instances/ajouter", {
            "csrf": csrf, "nom": "suivie", "adresse": "127.0.0.1", "port": str(self.follower_admin), "code": code})
        self.assertEqual((status, headers.get("location")), (303, "/instances"))
        stored = json.loads((self.master.root / "var" / "lib" / "admin" / "instances.json").read_text())
        item = stored["instances"][0]
        self.assertEqual(item["fingerprint"], self.fingerprint)  # empreinte epinglee
        follower_master = json.loads((self.follower.root / "var" / "lib" / "admin" / "maitre.json").read_text())
        self.assertNotIn(item["token"], json.dumps(follower_master))  # seulement le hache chez l'instance
        self.assertEqual(oct((self.master.root / "var" / "lib" / "admin" / "instances.json").stat().st_mode & 0o777),
                         oct(0o660))

        rows = self._rows(lambda rows: rows and rows[0]["cells"][3] != "-")
        self.assertEqual(rows[0]["id"], item["instance_id"])
        status, _headers, body = self._call("GET", f"/api/distant/{item['instance_id']}/vue/etat")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body).get("sections") or json.loads(body).get("loading"))

        fields = {"csrf": csrf, "action": "bannir", "adresse": "203.0.113.77", "duree": "1h", "raison": "maitre"}
        target = f"/instances/{item['instance_id']}/action"
        status, _headers, confirmation = self._call("POST", target, fields)
        self.assertIn('name="confirme" value="1"', confirmation)
        status, headers, _body = self._call("POST", target, {**fields, "confirme": "1"})
        self.assertEqual(status, 303)
        self.assertIn("203.0.113.77/32", self._blocklist())
        master_audit = (self.master.root / "var" / "log" / "admin-audit.log").read_text()
        follower_audit = (self.follower.root / "var" / "log" / "admin-audit.log").read_text()
        self.assertRegex(master_audit, r"action bannir .*instance='suivie' compte=admin .*-> ok")
        self.assertRegex(follower_audit, r"action bannir .*compte_maitre='admin' .*-> ok")
        self.assertIn("maitre accepte (code)", follower_audit)

        self.assertEqual(_cli(self.follower, "master", "revoke").returncode, 0)
        self._rows(lambda rows: "jeton" in rows[0]["cells"][2])

        identity = json.loads(_cli(self.master, "instances", "identity").stdout)
        accepted = _cli(self.follower, "master", "accept", "--master-id", identity["maitre_id"], "--master-name",
                        identity["nom"], "--rights", "lecture", "--replace")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        given = json.loads(accepted.stdout)
        self.assertEqual((given["empreinte"], given["port"]), (self.fingerprint, self.follower_admin))
        added = _cli(self.master, "instances", "add", "127.0.0.1", str(given["port"]), "--fingerprint",
                     given["empreinte"], "--name", "suivie", stdin=given["jeton"] + "\n")
        self.assertEqual(added.returncode, 0, added.stderr)
        rows = self._rows(lambda rows: rows and rows[0]["cells"][7] == "lecture")
        self.assertEqual(len(rows), 1)  # meme adresse et port : l'entree est remplacee
        page = self._call("GET", f"/instances/{item['instance_id']}/administration")[2]
        self.assertIn("lecture", page)
        self.assertNotIn(f'action="/instances/{item["instance_id"]}/action"', page)

    def test_link_from_the_instances_screen_runs_each_instance_own_command(self):
        commands = _ProjectCommands(self.follower, self.master)
        request = LocalLinkRequest(self.follower.root, "suivie", "127.0.0.1", self.follower_admin, self.master.root,
                                   "lecture")
        outcome = link_local_master(commands, request)
        self.assertTrue(outcome.ok, outcome.message)
        rows = self._rows(lambda rows: rows and rows[0]["cells"][3] != "-" and rows[0]["cells"][7] == "lecture")
        stored = json.loads((self.master.root / "var" / "lib" / "admin" / "instances.json").read_text())
        self.assertEqual(stored["instances"][0]["fingerprint"], self.fingerprint)
        outcome = link_local_master(commands, LocalLinkRequest(
            self.follower.root, "suivie", "127.0.0.1", self.follower_admin, self.master.root, "administration"))
        self.assertTrue(outcome.ok, outcome.message)  # meme maitre : pas de confirmation de remplacement
        rows = self._rows(lambda rows: rows and rows[0]["cells"][7] == "administration")
        self.assertEqual(len(rows), 1)
        self.assertIn("maitre accepte (commande)", (self.follower.root / "var" / "log" / "admin-audit.log").read_text())


class TestPythonEngine(_Case, unittest.TestCase):
    engine = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeEngine(_Case, unittest.TestCase):
    engine = "native"


if __name__ == "__main__":
    unittest.main()
