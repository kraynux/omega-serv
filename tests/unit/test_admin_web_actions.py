"""Tableau de bord web, lot 5 : actions du mode Administration (plan §6). Controles d'acces (role lecture, mode,
CSRF, nouvelle saisie apres 15 min avec l'action gardee), confirmation obligatoire, journal d'audit, cibles prises
seulement dans les listes du serveur (jamais un chemin ou un nom libre), texte echappe, rechargement."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from omega_serv.application.admin_web.actions import ActionOutcome, AdminActions, ArchiveLine
from omega_serv.application.admin_web.auth import REAUTH_SECONDS, AdminAuth
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.auth.password_hashing import hash_password

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


class _Blocklist:
    def __init__(self, entries=()):
        self.entries = list(entries)

    def list_entries(self):
        return tuple(self.entries)

    def add_entry(self, entry):
        self.entries = [e for e in self.entries if e.network != entry.network] + [entry]

    def remove_entry(self, network):
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.network != network]
        return len(self.entries) != before


class _Riposte:
    def __init__(self):
        self.state = {}
        self.commands = []

    def set_state(self, key, value):
        self.state[key] = value

    def get_state(self, key):
        return self.state.get(key)

    def append_audit(self, now, kind, detail):
        pass

    def add_command(self, kind, params, now):
        self.commands.append(kind)
        return len(self.commands)

    def close(self):
        pass


class _Clock:
    def now(self):
        return NOW


class _Sources:
    def __init__(self, root: Path):
        self.project_root = root
        self.clock = _Clock()
        self.blocklist_port = _Blocklist()
        self.riposte = _Riposte()
        self.calls: list[tuple[str, str]] = []
        self.reloads = 0
        self.archive_names = ["access.log.20261116.tar.gz"]
        self.deleted: list[str] = []
        self.config_value = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 8080},
            "options": {"waf": {"enabled": True}, "riposte": {"enabled": True},
                        "reverse_proxy": {"enabled": True, "zones": [
                            {"url_prefix": "/", "upstreams": [{"host": "127.0.0.1", "port": 9001}]}]}}})

    def config(self):
        return self.config_value

    def blocklist(self, config):
        return self.blocklist_port

    def incident_repository(self, config):
        return None

    def export_closed_incident(self, config, incident_id):
        pass

    def riposte_store(self, config, write):
        return self.riposte

    async def admin_call(self, port, method, path):
        self.calls.append((method, path))
        if method == "GET":
            return 200, {"backends": [{"zone": "/", "name": "127.0.0.1:9001", "address": "127.0.0.1:9001",
                                       "engine": "python", "status": "up"}]}
        return 200, {"status": "ok"}

    def file_size(self, path):
        return 10 if path.name == "access.log" else None

    def rotate_now(self, log_path, keep):
        return ActionOutcome(True, f"archive {log_path.name}")

    def archives(self):
        return [ArchiveLine(name, 100, "2026-11-16 12:00") for name in self.archive_names]

    def delete_archive(self, name):
        self.deleted.append(name)
        return True

    def reload_problem(self):
        return ""

    def request_reload(self):
        self.reloads += 1


class _Store:
    def __init__(self, accounts):
        self.accounts = tuple(accounts)


class TestAdministrationActions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.sources = _Sources(Path(self._tmp.name))
        self.accounts = _Store([AdminAccount("lecteur", hash_password("mot-de-passe-1"), "lecture"),
                                AdminAccount("admin", hash_password("mot-de-passe-2"), "administration")])
        self.now = [1_700_000_000.0]
        self.audit: list[str] = []
        self.auth = AdminAuth(lambda: self.accounts.accounts, lambda: self.now[0], self.audit.append, local_only=True,
                              used_backup_codes=set, mark_backup_code_used=lambda code: None)
        self.app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",)), self.auth, "prod",
                               actions=AdminActions(self.sources))

    def _request(self, method, target, body=b"", cookie=None):
        headers = [("Host", "127.0.0.1:8443")] + ([("Cookie", f"{COOKIE_NAME}={cookie}")] if cookie else [])
        return asyncio.run(self.app.handle(AdminRequest("127.0.0.1", method, target, tuple(headers), body)))

    def _login(self, user="admin", password="mot-de-passe-2", mode="administration"):
        body = urlencode({"identifiant": user, "mot_de_passe": password, "mode": mode}).encode()
        response = self._request("POST", "/connexion", body)
        token = dict(response.headers)["Set-Cookie"].split(";")[0].split("=", 1)[1]
        return token, self.auth.session(token)

    def _action(self, cookie, session, **fields):
        return self._request("POST", "/action", urlencode({"csrf": session.csrf, **fields}).encode(), cookie)

    def test_confirmation_then_action_then_notice_and_audit(self):
        cookie, session = self._login()
        page = self._request("GET", "/", cookie=cookie)
        self.assertIn(b'name="action" value="bannir"', page.body)
        self.assertIn(b"127.0.0.1:9001", page.body)  # backends
        confirm = self._action(cookie, session, action="bannir", adresse="203.0.113.7", duree="24h", raison="test")
        self.assertEqual(confirm.status, 200)
        self.assertIn(b'name="confirme" value="1"', confirm.body)
        self.assertEqual(self.sources.blocklist_port.entries, [])  # rien avant la confirmation
        done = self._action(cookie, session, action="bannir", adresse="203.0.113.7", duree="24h", raison="test",
                            confirme="1")
        self.assertEqual((done.status, dict(done.headers)["Location"]), (303, "/"))
        self.assertEqual([e.network for e in self.sources.blocklist_port.entries], ["203.0.113.7/32"])
        self.assertTrue(any("action bannir" in line and "-> ok" in line and "compte=admin" in line
                            for line in self.audit), self.audit)
        after = self._request("GET", "/", cookie=cookie)
        self.assertIn(b'class="notice tone-ok"', after.body)
        self.assertIn("Débannir".encode(), after.body)
        self.assertNotIn(b'class="notice', self._request("GET", "/", cookie=cookie).body)  # affiche une fois

    def test_reader_role_and_csrf_and_dashboard_mode_are_refused(self):
        cookie, session = self._login("lecteur", "mot-de-passe-1", "tableau")
        self.assertEqual(self._action(cookie, session, action="recharger", confirme="1").status, 403)
        self.assertTrue(any("role lecture" in line for line in self.audit))
        cookie, session = self._login(mode="tableau")
        self.assertEqual(self._request("POST", "/action", b"action=recharger&confirme=1", cookie).status, 403)
        self.assertEqual(self._action(cookie, session, action="recharger", confirme="1").status, 403)
        self.assertEqual(self._action(cookie, session, action="inconnue").status, 400)
        self.assertEqual(self.sources.reloads, 0)

    def test_reader_choosing_administration_is_told_once_why_it_lands_on_the_dashboard(self):
        """Essai de l'auteur du 2026-11-17 : compte « lecture », case Administration cochee, rien n'expliquait
        l'arrivee sur le tableau de bord."""
        cookie, session = self._login("lecteur", "mot-de-passe-1", "administration")
        self.assertEqual(session.mode, "tableau")
        page = self._request("GET", "/", cookie=cookie)
        self.assertIn(b'class="notice tone-warn"', page.body)
        self.assertIn("lecture seule".encode(), page.body)
        self.assertNotIn(b'class="notice', self._request("GET", "/", cookie=cookie).body)  # une seule fois
        cookie, _session = self._login("lecteur", "mot-de-passe-1", "tableau")
        self.assertNotIn(b'class="notice', self._request("GET", "/", cookie=cookie).body)  # rien demande : rien dit

    def test_unreadable_archives_never_break_the_page(self):
        """Essai de l'auteur du 2026-11-17 : var/backups ferme au compte du service -> PermissionError, page
        Administration jamais servie (ERR_EMPTY_RESPONSE)."""
        def refused():
            raise PermissionError(13, "Permission denied", "var/backups/logs")
        self.sources.archives = refused
        cookie, session = self._login()
        page = self._request("GET", "/", cookie=cookie)
        self.assertEqual(page.status, 200)
        self.assertIn("Archives illisibles par le service".encode(), page.body)
        refused_delete = self._action(cookie, session, action="supprimer_archive", archive="a.tar.gz", confirme="1")
        self.assertEqual(refused_delete.status, 303)
        self.assertEqual(self.sources.deleted, [])

    def test_reauth_keeps_the_pending_action(self):
        cookie, session = self._login()
        self.now[0] += REAUTH_SECONDS + 1
        response = self._action(cookie, session, action="recharger")
        self.assertEqual(dict(response.headers)["Location"], "/reconnexion")
        body = urlencode({"csrf": session.csrf, "mot_de_passe": "mot-de-passe-2"}).encode()
        again = self._request("POST", "/reconnexion", body, cookie)
        self.assertEqual(dict(again.headers)["Location"], "/confirmation")
        confirm = self._request("GET", "/confirmation", cookie=cookie)
        self.assertIn(b'name="action" value="recharger"', confirm.body)
        self.assertEqual(self.sources.reloads, 0)
        self._action(cookie, session, action="recharger", confirme="1")
        self.assertEqual(self.sources.reloads, 1)

    def test_targets_come_only_from_server_lists(self):
        cookie, session = self._login()
        self._action(cookie, session, action="supprimer_archive", archive="../../secure/auth/admin-web.json",
                     confirme="1")
        self._action(cookie, session, action="backend", zone="/", backend="10.0.0.1:22", etat="draining",
                     confirme="1")
        self._action(cookie, session, action="archiver", journal="../etc/passwd", confirme="1")
        self.assertEqual(self.sources.deleted, [])
        self.assertNotIn("POST", [method for method, _path in self.sources.calls])
        self.assertEqual(sum("-> echec" in line for line in self.audit), 3)
        self._action(cookie, session, action="backend", zone="/", backend="127.0.0.1:9001", etat="draining",
                     confirme="1")
        self.assertIn(("POST", "/.omega-serv-admin/health?zone=%2F&upstream=127.0.0.1%3A9001&status=draining"),
                      self.sources.calls)
        self._action(cookie, session, action="supprimer_archive", archive="access.log.20261116.tar.gz", confirme="1")
        self.assertEqual(self.sources.deleted, ["access.log.20261116.tar.gz"])

    def test_invalid_address_never_reaches_confirmation_and_text_is_escaped(self):
        cookie, session = self._login()
        response = self._action(cookie, session, action="bannir", adresse="10.0.0.0/8", duree="24h")
        self.assertEqual(dict(response.headers)["Location"], "/")
        self.assertIn(b'class="notice error"', self._request("GET", "/", cookie=cookie).body)
        self._action(cookie, session, action="bannir", adresse="198.51.100.4", duree="permanent",
                     raison="<script>x</script>", confirme="1")
        page = self._request("GET", "/", cookie=cookie).body
        self.assertNotIn(b"<script>x", page)
        self.assertIn(b"&lt;script&gt;x", page)

    def test_riposte_emergency_stop_and_resume(self):
        cookie, session = self._login()
        self._action(cookie, session, action="riposte_arret_lever", confirme="1")
        self.assertEqual(self.sources.riposte.state.get("emergency_stop"), "1")
        self.assertEqual(self.sources.riposte.commands, ["revoke_all"])
        self.assertIn(b"Reprendre", self._request("GET", "/", cookie=cookie).body)
        self._action(cookie, session, action="riposte_reprise", confirme="1")
        self.assertEqual(self.sources.riposte.state.get("emergency_stop"), "0")


if __name__ == "__main__":
    unittest.main()
