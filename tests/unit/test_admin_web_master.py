"""Tableau de bord web, lot 6 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §7 et §9.2) : instance maitre et
instances suivies, les deux cotes en memoire.

Le faux client du maitre envoie ses requetes directement a l'application web d'une instance suivie (memes routes,
memes controles) ; il peut jouer un intermediaire TLS (empreinte vue differente de celle de l'instance).
Attaques couvertes : jeton absent ou faux, maitre revoque ou remplace, code faux (3 essais ferment la fenetre),
intermediaire TLS, defi rejoue, droits de lecture seulement, certificat change apres l'appairage."""
from __future__ import annotations

import asyncio
import json
import unittest
from dataclasses import replace
from urllib.parse import urlencode

from omega_serv.application.admin_web.actions import (
    ActionOutcome,
    AdminState,
    ArchiveLine,
    BackendLine,
    LogLine,
    ManualBan,
    state_from_dict,
    state_to_dict,
)
from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.fleet import FleetService
from omega_serv.application.admin_web.master_link import MasterAccess, MasterLinkManager
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.master import (
    PAIRING_ALPHABET,
    Fleet,
    MasterIdentity,
    display_pairing_code,
    new_pairing_code,
    normalize_pairing_code,
)
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.ports.admin_remote_port import ProbeReply, RemoteReply

INSTANCE_FP = "aa" * 32
INTRUDER_FP = "bb" * 32
SETTINGS = AdminWebSettings(allowed_networks=("127.0.0.0/8", "10.0.0.0/8"))


class _MasterStore:
    def __init__(self):
        self.master = None
        self.window = None
        self.master_writes = 0

    def load_master(self):
        return self.master

    def save_master(self, master):
        self.master = master
        self.master_writes += 1

    def load_pairing(self):
        return self.window

    def save_pairing(self, window):
        self.window = window


class _FleetStore:
    def __init__(self):
        self.fleet = Fleet()
        self.ident = None

    def identity(self, new_id, default_name):
        if self.ident is None:
            self.ident = MasterIdentity(new_id(), default_name)
        return self.ident

    def load(self):
        return self.fleet

    def save(self, fleet):
        self.fleet = fleet


class _Dashboard:
    def summary(self):
        return {"running": True, "kind": "proxy", "rps": 1.5, "errors_5xx": 2, "bans": 3, "incidents": 1,
                "updated": "12:00:00"}

    def panel(self, name):
        return {"sections": [{"title": name.upper(), "rows": [], "table": [], "headers": [], "note": ""}]} \
            if name in ("etat", "flux", "ressources", "securite") else None


class _Actions:
    def __init__(self):
        self.done: list[dict] = []

    async def state(self):
        return AdminState(bans=[ManualBan("203.0.113.9/32", "<script>x</script>", None)],
                          logs=[LogLine("access", __import__("pathlib").Path("var/log/access.log"), 10)],
                          reload_problem="")

    async def run(self, params):
        self.done.append(params)
        return ActionOutcome(True, f"fait : {params['action']}")


class _Follower:
    """Une instance suivie : son application web, son maitre accepte, son audit."""

    def __init__(self, now):
        self.now = now
        self.store = _MasterStore()
        self.audit: list[str] = []
        self.actions = _Actions()
        counter = iter(range(1000))
        self.manager = MasterLinkManager(self.store, lambda: self.now[0], self.audit.append,
                                         token=lambda: f"jeton-{next(counter)}", randbelow=lambda n: 0)
        self.access = MasterAccess(self.store, lambda: self.now[0], self.audit.append, lambda: INSTANCE_FP,
                                   lambda: "suivie", token=lambda: f"jeton-code-{next(counter)}")
        auth = AdminAuth(lambda: (), lambda: self.now[0], self.audit.append, local_only=True,
                         used_backup_codes=set, mark_backup_code_used=lambda code: None)
        self.app = AdminWebApp(SETTINGS, auth, "suivie", _Dashboard(), self.actions, self.access)  # type: ignore[arg-type]


class _Client:
    """Client du maitre branche directement sur l'application de l'instance suivie."""

    def __init__(self, follower: _Follower, peer_ip: str = "10.0.0.2"):
        self.follower = follower
        self.peer_ip = peer_ip
        self.intruder = False
        self.calls: list[tuple[str, str]] = []

    async def call(self, address, port, *, use_tls, fingerprint, method, path, token="", body=None, account=""):
        self.calls.append((method, path))
        seen = INTRUDER_FP if self.intruder else INSTANCE_FP
        if fingerprint is not None and fingerprint != seen:
            return RemoteReply(0, fingerprint=seen, error="empreinte")
        headers = [("Host", f"{address}:{port}")] + ([("Authorization", f"Bearer {token}")] if token else [])
        raw = json.dumps(body).encode() if body is not None else b""
        response = await self.follower.app.handle(AdminRequest(self.peer_ip, method, path, tuple(headers), raw))
        try:
            payload = json.loads(response.body) if response.body else None
        except ValueError:
            payload = None
        return RemoteReply(response.status, payload, seen)

    async def probe(self, url):
        return ProbeReply(503, 12) if "panne" in url else ProbeReply(200, 7)


def _run(coroutine):
    return asyncio.run(coroutine)


class TestPairingCode(unittest.TestCase):
    def test_code_alphabet_display_and_normalisation(self):
        code = new_pairing_code(lambda n: 5)
        self.assertEqual(len(code), 8)
        self.assertTrue(all(char in PAIRING_ALPHABET for char in code))
        for ambiguous in "IL0O1":
            self.assertNotIn(ambiguous, PAIRING_ALPHABET)
        self.assertEqual(display_pairing_code("K7QF3M9X"), "K7QF-3M9X")
        self.assertEqual(normalize_pairing_code(" k7qf-3m9x "), "K7QF3M9X")
        self.assertEqual(normalize_pairing_code("K7QF-3M9O"), "")  # O n'existe pas dans l'alphabet
        self.assertEqual(normalize_pairing_code("K7QF"), "")


class TestFollowerSide(unittest.TestCase):
    def setUp(self):
        self.now = [1_700_000_000.0]
        self.follower = _Follower(self.now)

    def _call(self, path, token=None, method="GET", body=None):
        headers = [("Host", "x")] + ([("Authorization", f"Bearer {token}")] if token else [])
        raw = json.dumps(body).encode() if body is not None else b""
        response = _run(self.follower.app.handle(AdminRequest("10.0.0.2", method, path, tuple(headers), raw)))
        return response.status, (json.loads(response.body) if response.body else None)

    def test_accept_keeps_only_a_hash_and_one_master(self):
        manager = self.follower.manager
        outcome = manager.accept("1" * 32, "maitre A", "lecture", replace_existing=False, source="commande")
        self.assertTrue(outcome.ok)
        self.assertNotIn(outcome.token, json.dumps(self.follower.store.master.to_dict()))
        refused = manager.accept("2" * 32, "maitre B", "lecture", replace_existing=False, source="commande")
        self.assertEqual((refused.ok, refused.error, refused.replaced), (False, "exists", "maitre A"))
        self.assertFalse(manager.accept("pas-hexa", "x", "lecture", replace_existing=True, source="c").ok)
        replaced = manager.accept("2" * 32, "maitre B", "administration", replace_existing=True, source="commande")
        self.assertEqual(replaced.replaced, "maitre A")
        self.assertEqual(self._call("/api/maitre/resume", outcome.token)[0], 401)  # l'ancien est revoque aussitot
        self.assertEqual(self._call("/api/maitre/resume", replaced.token)[0], 200)
        self.assertTrue(any("remplace='maitre A'" in line for line in self.follower.audit))

    def test_token_checks_rights_audit_and_revocation(self):
        token = self.follower.manager.accept("1" * 32, "maitre", "lecture", replace_existing=False,
                                             source="commande").token
        self.assertEqual(self._call("/api/maitre/resume")[0], 401)
        self.assertEqual(self._call("/api/maitre/resume", "faux")[0], 401)
        self.assertEqual(sum("appel de maitre refuse" in line for line in self.follower.audit), 1)  # 1 par minute
        status, payload = self._call("/api/maitre/resume", token)
        self.assertEqual((status, payload["droits"], payload["rps"]), (200, "lecture", 1.5))
        self.assertEqual(self._call("/api/maitre/vue/etat", token)[0], 200)
        self.assertEqual(self._call("/api/maitre/vue/inconnue", token)[0], 404)
        self.assertEqual(self._call("/api/maitre/administration", token)[0], 403)
        action = {"params": {"action": "recharger"}, "compte": "alice"}
        self.assertEqual(self._call("/api/maitre/action", token, "POST", action)[0], 403)
        self.assertEqual(self.follower.actions.done, [])
        self.assertTrue(any("maitre en lecture seule" in line and "compte_maitre='alice'" in line
                            for line in self.follower.audit))
        self.follower.manager.revoke()
        self.assertEqual(self._call("/api/maitre/resume", token)[0], 401)

    def test_last_call_written_at_most_once_a_minute(self):
        token = self.follower.manager.accept("1" * 32, "m", "lecture", replace_existing=False, source="c").token
        writes = self.follower.store.master_writes
        for _ in range(5):
            self._call("/api/maitre/resume", token)
        self.assertEqual(self.follower.store.master_writes, writes + 1)
        self.now[0] += 61
        self._call("/api/maitre/resume", token)
        self.assertEqual(self.follower.store.master_writes, writes + 2)
        self.assertTrue(self.follower.store.master.last_call)

    def test_administration_rights_run_actions_with_double_identity(self):
        token = self.follower.manager.accept("1" * 32, "maitre", "administration", replace_existing=False,
                                             source="commande").token
        status, payload = self._call("/api/maitre/action", token, "POST",
                                     {"params": {"action": "bannir", "adresse": "203.0.113.5", "duree": "1h",
                                                 "inconnu": "x"}, "compte": "alice"})
        self.assertEqual((status, payload["ok"]), (200, True))
        self.assertEqual(self.follower.actions.done, [{"action": "bannir", "adresse": "203.0.113.5", "duree": "1h"}])
        self.assertTrue(any("action bannir" in line and "maitre='maitre'" in line and "compte_maitre='alice'" in line
                            and "-> ok" in line for line in self.follower.audit))
        self.assertEqual(self._call("/api/maitre/action", token, "POST", {"params": {"action": "rm -rf"}})[0], 400)
        status, state = self._call("/api/maitre/administration", token)
        self.assertEqual(status, 200)
        self.assertEqual(state["bans"][0]["reason"], "<script>x</script>")  # texte, echappe a l'affichage

    def test_no_pairing_without_an_open_window(self):
        self.assertEqual(self._call("/api/appairage/defi", method="POST")[0], 403)
        self.follower.manager.accept("1" * 32, "m", "lecture", replace_existing=False, source="c")
        self.assertEqual(self.follower.manager.open_pairing("lecture", replace_existing=False).error, "exists")
        self.assertTrue(self.follower.manager.open_pairing("lecture", replace_existing=True).ok)
        self.now[0] += 601
        self.assertEqual(self._call("/api/appairage/defi", method="POST")[0], 403)


class TestPairingAndFleet(unittest.TestCase):
    def setUp(self):
        self.now = [1_700_000_000.0]
        self.follower = _Follower(self.now)
        self.client = _Client(self.follower)
        self.master_audit: list[str] = []
        ids = iter(f"{i:012x}" for i in range(1, 1000))
        self.store = _FleetStore()
        self.fleet = FleetService(self.store, self.client, self.master_audit.append, "maitre@poste",
                                  new_master_id=lambda: "c" * 32, new_instance_id=lambda: next(ids))

    def _open(self, rights="administration"):
        return self.follower.manager.open_pairing(rights, replace_existing=True).code

    def test_pairing_by_code_pins_the_fingerprint_and_gives_a_working_token(self):
        code = self._open()
        outcome = _run(self.fleet.pair("", "10.0.0.5", 8443, display_pairing_code(code).lower()))
        self.assertTrue(outcome.ok, outcome.message)
        item = self.store.fleet.instances[0]
        self.assertEqual((item.name, item.fingerprint), ("suivie", INSTANCE_FP))
        self.assertEqual(self.follower.store.master.master_id, "c" * 32)
        self.assertEqual(self.follower.store.master.rights, "administration")
        self.assertIsNone(self.follower.store.window)  # usage unique
        overview = _run(self.fleet.overview())
        self.assertEqual(overview["rows"][0]["cells"][2], "en marche")
        self.assertEqual(overview["rows"][0]["tone"], "warn")  # un incident ouvert
        status, panel = _run(self.fleet.panel(item.instance_id, "etat"))
        self.assertEqual((status, panel["sections"][0]["title"]), (200, "ETAT"))
        outcome = _run(self.fleet.action(item, {"action": "recharger"}, "alice"))
        self.assertEqual((outcome.ok, outcome.message), (True, "fait : recharger"))
        state = _run(self.fleet.admin_state(item))
        self.assertIsInstance(state, AdminState)
        self.assertTrue(any("maitre accepte (code)" in line for line in self.follower.audit))
        self.assertTrue(any("instance suivie ajoutee (code)" in line for line in self.master_audit))

    def test_wrong_code_three_times_closes_the_window(self):
        code = self._open()
        wrong = "".join(PAIRING_ALPHABET[(PAIRING_ALPHABET.index(c) + 1) % len(PAIRING_ALPHABET)] for c in code)
        for attempt in range(3):
            outcome = _run(self.fleet.pair("", "10.0.0.5", 8443, wrong))
            self.assertFalse(outcome.ok)
            self.assertIn("Code faux" if attempt < 2 else "", outcome.message)
        self.assertIsNone(self.follower.store.window)
        self.assertFalse(_run(self.fleet.pair("", "10.0.0.5", 8443, code)).ok)  # meme le bon code : fenetre fermee
        self.assertIsNone(self.follower.store.master)
        self.assertEqual(self.store.fleet.instances, ())

    def test_tls_interception_is_detected_by_the_instance(self):
        code = self._open()
        self.client.intruder = True  # le maitre voit le certificat de l'intermediaire
        outcome = _run(self.fleet.pair("", "10.0.0.5", 8443, code))
        self.assertFalse(outcome.ok)
        self.assertIsNone(self.follower.store.master)
        self.assertEqual(self.follower.store.window.attempts, 1)

    def test_replayed_challenge_is_refused(self):
        self._open()
        nonce = _run(self.client.call("10.0.0.5", 8443, use_tls=True, fingerprint=None, method="POST",
                                      path="/api/appairage/defi")).payload["nonce"]
        body = {"nonce_instance": nonce, "nonce_maitre": "d" * 64, "maitre_id": "c" * 32, "preuve": "0" * 64}
        first = _run(self.client.call("10.0.0.5", 8443, use_tls=True, fingerprint=None, method="POST",
                                      path="/api/appairage/preuve", body=body))
        again = _run(self.client.call("10.0.0.5", 8443, use_tls=True, fingerprint=None, method="POST",
                                      path="/api/appairage/preuve", body=body))
        self.assertEqual((first.status, again.status, again.payload["error"]), (403, 400, "defi"))

    def test_changed_certificate_is_refused_and_reported_once(self):
        self.assertTrue(_run(self.fleet.pair("", "10.0.0.5", 8443, self._open())).ok)
        self.client.intruder = True
        calls = len(self.client.calls)
        for _ in range(2):
            self.fleet._overview_at = -10
            row = _run(self.fleet.overview())["rows"][0]
            self.assertIn("certificat changé", row["cells"][2])
        self.assertEqual(len(self.client.calls), calls + 2)
        self.assertEqual(sum("certificat change" in line for line in self.master_audit), 1)

    def test_revoked_master_and_read_only_rights_are_explained(self):
        self.assertTrue(_run(self.fleet.pair("", "10.0.0.5", 8443, self._open("lecture"))).ok)
        item = self.store.fleet.instances[0]
        self.assertIn("lecture", _run(self.fleet.admin_state(item)))
        self.assertFalse(_run(self.fleet.action(item, {"action": "recharger"}, "alice")).ok)
        self.follower.manager.revoke()
        self.fleet._overview_at = -10
        self.assertIn("jeton refusé", _run(self.fleet.overview())["rows"][0]["cells"][2])

    def test_direct_add_probe_and_remove(self):
        self.assertFalse(self.fleet.add_direct("x", "10.0.0.9", 8443, "jeton", "").ok)  # HTTP hors boucle locale
        self.assertFalse(self.fleet.add_direct("x", "10.0.0.9", 70000, "jeton", INSTANCE_FP).ok)
        self.assertTrue(self.fleet.add_direct("locale", "127.0.0.1", 8444, "jeton", "").ok)
        self.assertTrue(self.fleet.add_direct("locale bis", "127.0.0.1", 8444, "jeton2", "").ok)
        self.assertEqual(len(self.store.fleet.instances), 1)  # meme adresse et port : remplacee
        self.assertFalse(self.fleet.add_probe("x", "ftp://a").ok)
        self.assertTrue(self.fleet.add_probe("api", "http://10.0.0.7:8080/sante").ok)
        self.assertTrue(self.fleet.add_probe("panne", "http://10.0.0.8/panne").ok)
        rows = _run(self.fleet.overview())["rows"]
        self.assertEqual([row["tone"] for row in rows[1:]], ["ok", "error"])
        self.assertIn("HTTP 200 en 7 ms", rows[1]["cells"][2])
        probe_id = rows[1]["id"]
        self.assertTrue(self.fleet.remove(probe_id).ok)
        self.assertFalse(self.fleet.remove(probe_id).ok)
        self.assertEqual(len(self.store.fleet.instances), 2)


class TestMasterPages(unittest.TestCase):
    def setUp(self):
        self.now = [1_700_000_000.0]
        self.follower = _Follower(self.now)
        self.audit: list[str] = []
        accounts = (AdminAccount("lecteur", hash_password("mot-de-passe-1"), "lecture"),
                    AdminAccount("admin", hash_password("mot-de-passe-2"), "administration"))
        self.auth = AdminAuth(lambda: accounts, lambda: self.now[0], self.audit.append, local_only=True,
                              used_backup_codes=set, mark_backup_code_used=lambda code: None)
        self.store = _FleetStore()
        self.fleet = FleetService(self.store, _Client(self.follower), self.audit.append, "maitre@poste",
                                  new_master_id=lambda: "c" * 32, new_instance_id=lambda: "0123456789ab")
        self.app = AdminWebApp(SETTINGS, self.auth, "maitre", _Dashboard(), _Actions(), fleet=self.fleet)  # type: ignore[arg-type]

    def _request(self, method, target, form=None, cookie=None):
        headers = [("Host", "127.0.0.1:8443")] + ([("Cookie", f"{COOKIE_NAME}={cookie}")] if cookie else [])
        body = urlencode(form).encode() if form is not None else b""
        return _run(self.app.handle(AdminRequest("127.0.0.1", method, target, tuple(headers), body)))

    def _login(self, user="admin", password="mot-de-passe-2", mode="administration"):
        response = self._request("POST", "/connexion", {"identifiant": user, "mot_de_passe": password, "mode": mode})
        token = dict(response.headers)["Set-Cookie"].split(";")[0].split("=", 1)[1]
        return token, self.auth.session(token)

    def test_pair_from_the_page_then_remote_action_with_confirmation_and_double_audit(self):
        cookie, session = self._login()
        page = self._request("GET", "/instances", cookie=cookie)
        self.assertIn(b'action="/instances/ajouter"', page.body)
        code = self.follower.manager.open_pairing("administration", replace_existing=False).code
        done = self._request("POST", "/instances/ajouter", {"csrf": session.csrf, "adresse": "10.0.0.5",
                                                            "port": "8443", "code": code}, cookie)
        self.assertEqual(dict(done.headers)["Location"], "/instances")
        self.assertIn(b'class="notice tone-ok"', self._request("GET", "/instances", cookie=cookie).body)
        rows = json.loads(self._request("GET", "/api/instances", cookie=cookie).body)["rows"]
        self.assertEqual(rows[0]["id"], "0123456789ab")
        view = self._request("GET", "/instances/0123456789ab", cookie=cookie)
        self.assertIn(b'data-api="/api/distant/0123456789ab/vue/etat"', view.body)
        remote = json.loads(self._request("GET", "/api/distant/0123456789ab/vue/flux", cookie=cookie).body)
        self.assertEqual(remote["sections"][0]["title"], "FLUX")
        admin = self._request("GET", "/instances/0123456789ab/administration", cookie=cookie)
        self.assertIn(b'action="/instances/0123456789ab/action"', admin.body)
        self.assertNotIn(b'action="/action"', admin.body)
        self.assertNotIn(b"<script>x</script>", admin.body)  # raison du ban venue de l'instance : echappee
        fields = {"csrf": session.csrf, "action": "debannir", "reseau": "203.0.113.9/32"}
        confirm = self._request("POST", "/instances/0123456789ab/action", fields, cookie)
        self.assertIn(b'name="confirme" value="1"', confirm.body)
        self.assertEqual(self.follower.actions.done, [])
        done = self._request("POST", "/instances/0123456789ab/action", {**fields, "confirme": "1"}, cookie)
        self.assertEqual(dict(done.headers)["Location"], "/instances/0123456789ab/administration")
        self.assertEqual(self.follower.actions.done, [{"action": "debannir", "reseau": "203.0.113.9/32"}])
        self.assertTrue(any("action debannir" in line and "instance='suivie'" in line and "compte=admin" in line
                            for line in self.audit))
        self.assertTrue(any("action debannir" in line and "compte_maitre='admin'" in line
                            for line in self.follower.audit))

    def test_reader_sees_instances_but_cannot_manage_or_act(self):
        self.fleet.add_direct("locale", "127.0.0.1", 8444, "jeton", "")
        cookie, session = self._login("lecteur", "mot-de-passe-1", "tableau")
        page = self._request("GET", "/instances", cookie=cookie)
        self.assertEqual(page.status, 200)
        self.assertNotIn(b"/instances/ajouter", page.body)
        item_id = self.store.fleet.instances[0].instance_id
        for path, form in (("/instances/ajouter", {"adresse": "10.0.0.5", "port": "1", "code": "AAAAAAAA"}),
                           ("/instances/retirer", {"instance": item_id, "confirme": "1"}),
                           (f"/instances/{item_id}/action", {"action": "recharger", "confirme": "1"})):
            self.assertEqual(self._request("POST", path, {"csrf": session.csrf, **form}, cookie).status, 403)
        self.assertEqual(len(self.store.fleet.instances), 1)
        admin = self._request("GET", f"/instances/{item_id}/administration", cookie=cookie)
        self.assertEqual(dict(admin.headers)["Location"], f"/instances/{item_id}")

    def test_remove_needs_confirmation_and_csrf(self):
        self.fleet.add_direct("locale", "127.0.0.1", 8444, "jeton", "")
        item_id = self.store.fleet.instances[0].instance_id
        cookie, session = self._login()
        self.assertEqual(self._request("POST", "/instances/retirer", {"instance": item_id, "confirme": "1"},
                                       cookie).status, 403)
        confirm = self._request("POST", "/instances/retirer", {"csrf": session.csrf, "instance": item_id}, cookie)
        self.assertIn(b'name="confirme" value="1"', confirm.body)
        self.assertEqual(len(self.store.fleet.instances), 1)
        self._request("POST", "/instances/retirer", {"csrf": session.csrf, "instance": item_id, "confirme": "1"},
                      cookie)
        self.assertEqual(self.store.fleet.instances, ())

    def test_unknown_or_malformed_instance_ids(self):
        cookie, _session = self._login()
        for path in ("/instances/zzz", "/instances/0123456789ab", "/instances/../etc"):
            self.assertEqual(self._request("GET", path, cookie=cookie).status, 404)
        self.assertEqual(self._request("GET", "/api/distant/0123456789ab/vue/etat", cookie=cookie).status, 404)
        self.assertEqual(self._request("GET", "/api/instances").status, 401)


class TestStateTransport(unittest.TestCase):
    def test_round_trip_and_malformed_data(self):
        state = AdminState(bans=[ManualBan("203.0.113.1/32", "r", "2026-11-17T00:00:00+00:00")],
                           riposte_stopped=False, backends=[BackendLine("/api/", "b1", "up")], backends_shown=True,
                           logs=[LogLine("access", __import__("pathlib").Path("/x/var/log/access.log"), None)],
                           archives=[ArchiveLine("a.tar.gz", 5, "2026-11-16 12:00")])
        back = state_from_dict(json.loads(json.dumps(state_to_dict(state))))
        self.assertEqual(back.bans, state.bans)
        self.assertEqual(back.backends, state.backends)
        self.assertEqual(back.logs[0].path.name, "access.log")
        self.assertEqual(str(back.logs[0].path), "access.log")  # jamais un chemin de l'autre machine
        for bad in (None, [], {"bans": "x"}, {"riposte_stopped": "oui"}, {"logs": [{"key": "a", "name": "b",
                                                                                     "size": "10"}]}):
            with self.assertRaises(ValueError):
                state_from_dict(bad)
        self.assertEqual(replace(back, reload_problem="x").reload_problem, "x")


if __name__ == "__main__":
    unittest.main()
