# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tableau de bord web, lot 5 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §6) : actions du mode Administration de
bout en bout, vrai serveur, deux moteurs :

- bannir puis debannir une adresse (blocklist reelle, confirmation obligatoire) ;
- DRAINING puis retour a l'automatique d'un backend (lu ensuite par la route d'administration du serveur) ;
- archiver access.log puis supprimer l'archive ;
- recharger : le signal arrive au superviseur, l'administration redemarre et la session reste ouverte ;
- chaque action dans le journal d'audit.

Le binaire natif n'est pas versionne : sans build, la moitie native est sautee."""
from __future__ import annotations

import http.client
import json
import re
import time
import unittest
from urllib.parse import urlencode

from omega_serv.domain.security.auth.password_hashing import hash_password
from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject
from tests.integration.test_admin_web_process import _free_port, _wait_log, _wait_port


class _Case:
    engine = "python"

    def setUp(self):
        self.admin_port = _free_port()
        self.project = ProxyProject(
            self.engine, _free_port(), proxy={"engine": "native"} if self.engine == "native" else None,
            options={"waf": {"enabled": True},
                     "admin_web": {"enabled": True, "bind": "127.0.0.1", "port": self.admin_port, "tls": "none"}})
        self.addCleanup(self.project.stop)
        auth = self.project.root / "secure" / "auth"
        auth.mkdir(parents=True, exist_ok=True)
        (auth / "admin-web.json").write_text(json.dumps({"version": 1, "accounts": [
            {"username": "admin", "password_hash": hash_password("mot-de-passe-2"), "role": "administration"}]}))
        self.project.start()
        self.assertTrue(_wait_port(self.admin_port))
        status, headers, _body = self._call("POST", "/connexion", {
            "identifiant": "admin", "mot_de_passe": "mot-de-passe-2", "mode": "administration"})
        self.assertEqual(status, 303)
        self.cookie = headers["set-cookie"].split(";")[0]

    def _call(self, method: str, path: str, form: dict | None = None) -> tuple[int, dict[str, str], str]:
        connection = http.client.HTTPConnection("127.0.0.1", self.admin_port, timeout=10)
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

    def _page(self) -> str:
        status, _headers, body = self._call("GET", "/")
        self.assertEqual(status, 200)
        return body

    def _act(self, **fields: str) -> str:
        csrf = re.search(r'name="csrf" value="([^"]+)"', self._page()).group(1)
        status, _headers, confirmation = self._call("POST", "/action", {"csrf": csrf, **fields})
        self.assertEqual(status, 200)
        self.assertIn('name="confirme" value="1"', confirmation)
        status, headers, _body = self._call("POST", "/action", {"csrf": csrf, **fields, "confirme": "1"})
        self.assertEqual((status, headers.get("location")), (303, "/"))
        return self._page()  # porte le resultat de l'action

    def _blocklist(self) -> list[str]:
        path = self.project.root / "var" / "lib" / "waf" / "blocklist.json"
        return [entry["network"] for entry in json.loads(path.read_text())["entries"]]

    def _backend_status(self) -> str:
        status, _headers, body, _raw = self.project.request("GET", "/.omega-serv-admin/backends")
        self.assertEqual(status, 200)
        return json.loads(body)["backends"][0]["status"]

    def test_ban_backend_archive_and_reload(self):
        page = self._act(action="bannir", adresse="203.0.113.50", duree="1h", raison="essai web")
        self.assertIn("203.0.113.50/32", self._blocklist())
        self.assertIn('class="notice tone-ok"', page)
        page = self._act(action="debannir", reseau="203.0.113.50/32")
        self.assertNotIn("203.0.113.50/32", self._blocklist())

        name = re.search(r'name="backend" value="([^"]+)"', page).group(1)
        self._act(action="backend", zone="/api/", backend=name, etat="draining")
        self.assertEqual(self._backend_status(), "draining")
        self._act(action="backend", zone="/api/", backend=name, etat="clear")
        deadline = time.monotonic() + 5  # natif : son etat suivant arrive en 1 s environ
        while self._backend_status() == "draining" and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertNotEqual(self._backend_status(), "draining")

        self.project.request("GET", "/")
        page = self._act(action="archiver", journal="access")
        archives = sorted((self.project.root / "var" / "backups" / "logs").glob("access.log.*.tar.gz"))
        self.assertEqual(len(archives), 1, page)
        self._act(action="supprimer_archive", archive=archives[0].name)
        self.assertFalse(archives[0].exists())

        error_log = self.project.root / "var" / "log" / "error.log"
        self.assertEqual(_wait_log(error_log, "administration web : ecoute sur").count("ecoute sur"), 1)
        self._act(action="recharger")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and error_log.read_text().count("administration web : ecoute sur") < 2:
            time.sleep(0.2)
        self.assertEqual(error_log.read_text().count("administration web : ecoute sur"), 2)
        self.assertTrue(_wait_port(self.admin_port))
        self.assertIn('name="action" value="recharger"', self._page())  # session toujours ouverte

        audit = (self.project.root / "var" / "log" / "admin-audit.log").read_text()
        for action in ("bannir", "debannir", "backend", "archiver", "supprimer_archive", "recharger"):
            self.assertRegex(audit, rf"action {action} .*compte=admin .*-> ok")


class TestPythonEngine(_Case, unittest.TestCase):
    engine = "python"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeEngine(_Case, unittest.TestCase):
    engine = "native"


if __name__ == "__main__":
    unittest.main()
