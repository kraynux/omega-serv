# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sessions ouvertes du panneau web (etude modules, module 5, 2026-11-17) : un compte administration voit et ferme
toutes les sessions, un compte lecture les siennes ; liste publiee pour la TUI sans jeton ; fermeture demandee par
la TUI ; tout est audite."""
from __future__ import annotations

import asyncio
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.session_publisher import SessionPublisher
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.infrastructure.admin_web.session_files import SESSIONS_RELATIVE_PATH, SessionFiles
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestSessions(unittest.TestCase):
    def setUp(self):
        accounts = (AdminAccount("lecteur", hash_password("mot-de-passe-1"), "lecture"),
                    AdminAccount("admin", hash_password("mot-de-passe-2"), "administration"))
        self.audit: list[str] = []
        self.auth = AdminAuth(lambda: accounts, lambda: 1_700_000_000.0, self.audit.append, local_only=True,
                              used_backup_codes=set, mark_backup_code_used=lambda code: None)
        self.app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",)), self.auth, "prod")

    def _request(self, method, target, body=b"", cookie="", ip="127.0.0.1"):
        headers = (("Host", "127.0.0.1:9643"), ("Cookie", cookie))
        return asyncio.run(self.app.handle(AdminRequest(ip, method, target, headers, body)))

    def _login(self, user, password, ip="127.0.0.1"):
        body = urlencode({"identifiant": user, "mot_de_passe": password}).encode()
        token = dict(self._request("POST", "/connexion", body, ip=ip).headers)["Set-Cookie"].split(";")[0]
        token = token.split("=", 1)[1]
        return f"{COOKIE_NAME}={token}", self.auth.session(token)

    def test_admin_sees_and_closes_any_session_reader_only_its_own(self):
        reader_cookie, reader = self._login("lecteur", "mot-de-passe-1", "127.0.0.2")
        admin_cookie, admin = self._login("admin", "mot-de-passe-2")
        page = self._request("GET", "/sessions", cookie=admin_cookie).body.decode()
        self.assertIn("127.0.0.2", page)
        self.assertIn("(cette session)", page)
        self.assertNotIn(reader.token, page)  # jamais le jeton, seulement l'identifiant public
        self.assertIn(reader.public_id, page)
        reader_page = self._request("GET", "/sessions", cookie=reader_cookie).body.decode()
        self.assertNotIn(admin.public_id, reader_page)
        refused = urlencode({"csrf": reader.csrf, "session": admin.public_id}).encode()
        self._request("POST", "/sessions/fermer", refused, cookie=reader_cookie)
        self.assertIsNotNone(self.auth.session(admin.token))  # un lecteur ne ferme pas la session d'un autre
        self.assertTrue(any("fermeture de session refusee" in line for line in self.audit))
        forged = urlencode({"csrf": "faux", "session": reader.public_id}).encode()
        self.assertEqual(self._request("POST", "/sessions/fermer", forged, cookie=admin_cookie).status, 403)
        done = self._request("POST", "/sessions/fermer",
                             urlencode({"csrf": admin.csrf, "session": reader.public_id}).encode(), cookie=admin_cookie)
        self.assertEqual(dict(done.headers)["Location"], "/sessions")
        self.assertIsNone(self.auth.session(reader.token))  # deconnecte tout de suite
        self.assertTrue(any("session fermee par admin compte=lecteur" in line for line in self.audit))
        self.assertIn("Session fermée.", self._request("GET", "/sessions", cookie=admin_cookie).body.decode())

    def test_published_for_the_tui_without_tokens_and_closed_on_request(self):
        _cookie, reader = self._login("lecteur", "mot-de-passe-1", "127.0.0.2")
        with tempfile.TemporaryDirectory() as name:
            files = SessionFiles(LocalFilesystem(), Path(name), clock=lambda: 1_700_000_000.0)
            publisher = SessionPublisher(files, lambda: self.auth)
            publisher.tick()
            raw = (Path(name) / SESSIONS_RELATIVE_PATH).read_text()
            self.assertNotIn(reader.token, raw)
            stamp, sessions = files.published()
            self.assertEqual((sessions[0]["compte"], sessions[0]["adresse"], sessions[0]["id"]),
                             ("lecteur", "127.0.0.2", reader.public_id))
            files.request_close(reader.public_id)
            files.request_close("pas-un-id")
            publisher.tick()
            self.assertIsNone(self.auth.session(reader.token))
            self.assertEqual(files.published()[1], [])
            self.assertEqual(files.take_close_requests(), [])  # demande consommee
            self.assertTrue(any(re.search(r"session fermee par TUI compte=lecteur", line) for line in self.audit))


if __name__ == "__main__":
    unittest.main()
