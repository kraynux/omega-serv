"""Tableau de bord web, lot 3 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §3, §3.1, §5.1 ; decisions de l'auteur
du 2026-11-16) : TOTP (vecteurs de la RFC 6238), QR code (decode par zbarimg), comptes, authentification, routage."""
from __future__ import annotations

import asyncio
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from omega_serv.application.admin_web import manage_accounts as accounts_api
from omega_serv.application.admin_web.auth import REAUTH_SECONDS, SESSION_IDLE_SECONDS, AdminAuth
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.domain.admin_web import qr, totp
from omega_serv.domain.admin_web.accounts import AdminAccount, accounts_missing_totp
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.security.auth.password_hashing import hash_password

_RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890" en base32 (RFC 6238, annexe B, SHA1)


class _Store:
    def __init__(self, accounts=()):
        self.accounts = tuple(accounts)

    def load(self):
        return self.accounts

    def save(self, accounts):
        self.accounts = tuple(accounts)


class _Clock:
    def __init__(self, value: float = 1_700_000_000.0):
        self.value = value

    def __call__(self) -> float:
        return self.value


class TestTotp(unittest.TestCase):
    def test_rfc6238_vectors(self):
        for unix, expected in ((59, "287082"), (1111111109, "081804"), (1111111111, "050471"),
                               (1234567890, "005924"), (2000000000, "279037")):
            self.assertEqual(totp.code_at(_RFC_SECRET, totp.step_of(unix)), expected)

    def test_window_and_replay(self):
        now = 1234567890
        code = totp.code_at(_RFC_SECRET, totp.step_of(now - 30))  # periode precedente : acceptee
        step = totp.verify(_RFC_SECRET, code, now, None)
        self.assertEqual(step, totp.step_of(now - 30))
        self.assertIsNone(totp.verify(_RFC_SECRET, code, now, step))  # deja utilise
        self.assertIsNone(totp.verify(_RFC_SECRET, totp.code_at(_RFC_SECRET, totp.step_of(now - 90)), now, None))
        self.assertIsNone(totp.verify(_RFC_SECRET, "12345", now, None))
        self.assertIsNone(totp.verify("pas du base32 !", "123456", now, None))

    def test_secret_and_link(self):
        secret = totp.new_secret(bytes(range(20)))
        self.assertEqual(len(secret), 32)
        self.assertEqual(totp.grouped("ABCDEFGH"), "ABCD EFGH")
        uri = totp.otpauth_uri(secret, "admin", "omega-serv prod")
        self.assertTrue(uri.startswith("otpauth://totp/omega-serv%20prod%3Aadmin?secret="))
        self.assertIn("issuer=omega-serv%20prod", uri)


def _png(modules: list[list[bool]], path: Path, scale: int = 6, quiet: int = 4) -> None:
    size = len(modules) + 2 * quiet
    rows = []
    for y in range(size * scale):
        row = bytearray([0])
        for x in range(size * scale):
            mx, my = x // scale - quiet, y // scale - quiet
            dark = 0 <= mx < len(modules) and 0 <= my < len(modules) and modules[my][mx]
            row.append(0 if dark else 255)
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size * scale, size * scale, 8, 0, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows)))
                     + chunk(b"IEND", b""))


@unittest.skipUnless(shutil.which("zbarimg"), "zbarimg absent : le QR code n'est pas decode")
class TestQr(unittest.TestCase):
    def test_codes_decode_back_to_their_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, text in enumerate(("A", "x" * 50, totp.otpauth_uri(_RFC_SECRET, "admin", "omega-serv"),
                                      "y" * 150, "z" * 213)):
                matrix = qr.encode(text)
                path = Path(tmp) / f"{i}.png"
                _png(matrix, path)
                decoded = subprocess.run(["zbarimg", "-q", "--raw", str(path)], capture_output=True, text=True,
                                         check=False)
                self.assertEqual(decoded.stdout.rstrip("\n"), text, f"version {(len(matrix) - 17) // 4}")

    def test_too_long_is_refused_and_text_rendering(self):
        with self.assertRaises(ValueError):
            qr.encode("w" * 214)
        lines = qr.to_text(qr.encode("A"))
        self.assertEqual(len(lines[0]), 21 + 4)  # version 1 + zone de silence de 2 de chaque cote


class TestManageAccounts(unittest.TestCase):
    def test_add_rules_and_totp_two_steps(self):
        store = _Store()
        self.assertFalse(accounts_api.add_account(store, "a b", "x" * 12, "lecture").success)
        self.assertFalse(accounts_api.add_account(store, "admin", "court", "lecture").success)
        self.assertFalse(accounts_api.add_account(store, "admin", "x" * 12, "chef").success)
        self.assertTrue(accounts_api.add_account(store, "admin", "un-mot-de-passe", "administration").success)
        self.assertFalse(accounts_api.add_account(store, "admin", "un-mot-de-passe", "lecture").success)  # doublon
        self.assertNotIn("un-mot-de-passe", store.accounts[0].password_hash)
        self.assertEqual(accounts_missing_totp(store.accounts), ["admin"])
        secret = accounts_api.new_totp_secret(lambda n: bytes(range(n)))
        self.assertFalse(accounts_api.confirm_totp(store, "admin", secret, "000000", lambda: 0.0).success)
        self.assertFalse(store.accounts[0].totp_enabled)  # code faux : rien d'enregistre
        result = accounts_api.confirm_totp(store, "admin", secret, totp.code_at(secret, totp.step_of(1000)),
                                           lambda: 1000.0)
        self.assertTrue(result.success)
        self.assertEqual(len(result.backup_codes), 10)
        self.assertTrue(store.accounts[0].totp_enabled)
        self.assertEqual(accounts_missing_totp(store.accounts), [])
        self.assertTrue(accounts_api.disable_totp(store, "admin").success)
        self.assertEqual(store.accounts[0].backup_code_hashes, ())
        self.assertEqual(accounts_api.normalize_backup_code(" ab cd-ef gh "), "ABCD-EFGH")


    def test_remaining_and_new_backup_codes(self):
        store = _Store([AdminAccount("admin", hash_password("un-mot-de-passe"), "administration")])
        self.assertFalse(accounts_api.regenerate_backup_codes(store, "admin").success)  # sans TOTP : refuse
        secret = accounts_api.new_totp_secret(lambda n: bytes(range(n)))
        accounts_api.confirm_totp(store, "admin", secret, totp.code_at(secret, totp.step_of(1000)), lambda: 1000.0)
        account = store.accounts[0]
        used = {account.backup_code_hashes[0], account.backup_code_hashes[1]}
        self.assertEqual(accounts_api.remaining_backup_codes(account, used), 8)
        result = accounts_api.regenerate_backup_codes(store, "admin")
        self.assertTrue(result.success)
        self.assertEqual(len(result.backup_codes), 10)
        renewed = store.accounts[0]
        self.assertEqual(renewed.totp_secret, secret)  # le telephone ne change pas
        self.assertEqual(accounts_api.remaining_backup_codes(renewed, used), 10)
        self.assertTrue(set(renewed.backup_code_hashes).isdisjoint(account.backup_code_hashes))

def _auth(accounts, clock, *, local_only=True, audit=None, used=None):
    used = used if used is not None else set()
    return AdminAuth(lambda: tuple(accounts.accounts), clock, (audit if audit is not None else []).append,
                     local_only=local_only,
                     used_backup_codes=lambda: set(used), mark_backup_code_used=used.add)


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.store = _Store([AdminAccount("lecteur", hash_password("mot-de-passe-1"), "lecture"),
                             AdminAccount("admin", hash_password("mot-de-passe-2"), "administration")])
        self.clock = _Clock()
        self.audit: list[str] = []
        self.auth = _auth(self.store, self.clock, audit=self.audit)

    def test_login_modes_and_one_generic_error(self):
        self.assertEqual(self.auth.login("10.0.0.1", "admin", "faux", "", "tableau").error, "invalid")
        self.assertEqual(self.auth.login("10.0.0.1", "inconnu", "faux", "", "tableau").error, "invalid")
        reader = self.auth.login("10.0.0.1", "lecteur", "mot-de-passe-1", "", "administration").session
        self.assertEqual(reader.mode, "tableau")  # role lecture : jamais Administration
        self.assertEqual(self.auth.switch_mode(reader, "administration", "10.0.0.1"), "refused")
        admin = self.auth.login("10.0.0.1", "admin", "mot-de-passe-2", "", "administration").session
        self.assertEqual(admin.mode, "administration")
        self.assertIs(self.auth.session(admin.token), admin)
        self.assertTrue(any("echec de connexion" in line for line in self.audit))
        self.assertFalse(any("mot-de-passe" in line for line in self.audit))  # jamais de secret dans l'audit

    def test_lockout_doubles_and_counts_per_account(self):
        for _ in range(5):
            self.auth.login("10.0.0.2", "admin", "faux", "", "tableau")
        locked = self.auth.login("10.0.0.2", "admin", "mot-de-passe-2", "", "tableau")
        self.assertEqual((locked.error, locked.retry_after), ("locked", 60))
        # Scan de securite n° 2 (F28) : le verrou suit le couple compte + adresse ; une autre adresse permise ne
        # bloque plus l'administrateur legitime.
        self.assertIsNotNone(self.auth.login("10.0.0.3", "admin", "mot-de-passe-2", "", "tableau").session)
        self.clock.value += 61
        self.assertIsNotNone(self.auth.login("10.0.0.2", "admin", "mot-de-passe-2", "", "tableau").session)

    def test_idle_expiry_reauth_and_account_change_close_sessions(self):
        session = self.auth.login("10.0.0.1", "admin", "mot-de-passe-2", "", "tableau").session
        self.clock.value += REAUTH_SECONDS + 1
        self.assertIsNotNone(self.auth.session(session.token))
        self.assertEqual(self.auth.switch_mode(session, "administration", "10.0.0.1"), "reauth")
        self.assertIsNone(self.auth.reauthenticate(session, "faux", "", "10.0.0.1").session)
        self.assertIsNotNone(self.auth.reauthenticate(session, "mot-de-passe-2", "", "10.0.0.1").session)
        self.assertEqual(session.mode, "administration")
        accounts_api.set_password(self.store, "admin", "nouveau-mot-de-passe")
        self.assertIsNone(self.auth.session(session.token))  # compte modifie : session fermee
        other = self.auth.login("10.0.0.1", "lecteur", "mot-de-passe-1", "", "tableau").session
        self.clock.value += SESSION_IDLE_SECONDS + 1
        self.assertIsNone(self.auth.session(other.token))

    def test_totp_backup_code_and_rule_b(self):
        secret = accounts_api.new_totp_secret(lambda n: bytes(range(n)))
        result = accounts_api.confirm_totp(self.store, "admin", secret, totp.code_at(secret, totp.step_of(self.clock())),
                                           self.clock)
        self.assertEqual(self.auth.login("10.0.0.1", "admin", "mot-de-passe-2", "", "tableau").error, "invalid")
        code = totp.code_at(secret, totp.step_of(self.clock()) + 1)
        self.assertIsNotNone(self.auth.login("10.0.0.1", "admin", "mot-de-passe-2", code, "tableau").session)
        self.assertIsNone(self.auth.login("10.0.0.1", "admin", "mot-de-passe-2", code, "tableau").session)  # rejeu
        backup = result.backup_codes[0]
        self.assertIsNotNone(self.auth.login("10.0.0.4", "admin", "mot-de-passe-2", backup.lower(), "tableau").session)
        self.assertIsNone(self.auth.login("10.0.0.4", "admin", "mot-de-passe-2", backup, "tableau").session)  # use
        remote = _auth(_Store([AdminAccount("admin", hash_password("mot-de-passe-2"), "administration")]),
                       self.clock, local_only=False)
        self.assertEqual(remote.login("10.0.0.1", "admin", "mot-de-passe-2", "", "tableau").error,
                         "totp_setup_required")


    def test_new_backup_codes_keep_sessions_and_retire_old_codes(self):
        secret = accounts_api.new_totp_secret(lambda n: bytes(range(n)))
        first = accounts_api.confirm_totp(self.store, "admin", secret,
                                          totp.code_at(secret, totp.step_of(self.clock())), self.clock)
        session = self.auth.login("10.0.0.1", "admin", "mot-de-passe-2", first.backup_codes[0], "tableau").session
        renewed = accounts_api.regenerate_backup_codes(self.store, "admin")
        self.assertIs(self.auth.session(session.token), session)  # session gardee
        self.assertIsNone(self.auth.login("10.0.0.5", "admin", "mot-de-passe-2", first.backup_codes[1],
                                          "tableau").session)  # ancien code : refuse
        self.assertIsNotNone(self.auth.login("10.0.0.5", "admin", "mot-de-passe-2", renewed.backup_codes[0],
                                             "tableau").session)

class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.store = _Store([AdminAccount("admin", hash_password("mot-de-passe-2"), "administration")])
        self.clock = _Clock()
        settings = AdminWebSettings(allowed_networks=("127.0.0.0/8",))
        self.app = AdminWebApp(settings, _auth(self.store, self.clock), "prod")

    def _request(self, method, target, body=b"", cookie=None, origin=None, peer="127.0.0.1"):
        headers = [("Host", "127.0.0.1:8443")]
        if cookie:
            headers.append(("Cookie", f"{COOKIE_NAME}={cookie}"))
        if origin:
            headers.append(("Origin", origin))
        return asyncio.run(self.app.handle(AdminRequest(peer, method, target, tuple(headers), body)))

    def _login(self) -> str:
        response = self._request("POST", "/connexion", b"identifiant=admin&mot_de_passe=mot-de-passe-2&mode=tableau")
        self.assertEqual(response.status, 303)
        cookie = dict(response.headers)["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        return cookie.split(";")[0].split("=", 1)[1]

    def test_network_login_page_css_and_redirects(self):
        self.assertEqual(self._request("GET", "/", peer="203.0.113.9").status, 403)
        self.assertEqual(self._request("GET", "/").status, 303)  # pas de session : vers la connexion
        page = self._request("GET", "/connexion")
        self.assertEqual(page.status, 200)
        self.assertIn(b'name="mode" value="administration"', page.body)
        self.assertIn(b"/static/admin.css", page.body)
        self.assertIn("style-src 'self'", dict(page.headers)["Content-Security-Policy"])
        # Retour de l'auteur (2026-11-17) : avec no-referrer, un navigateur envoie « Origin: null » en POST de formulaire,
        # refuse ensuite par le controle d'origine (403 a chaque connexion depuis un autre appareil).
        self.assertEqual(dict(page.headers)["Referrer-Policy"], "same-origin")
        form = b"identifiant=admin&mot_de_passe=mot-de-passe-2&mode=tableau"
        self.assertEqual(self._request("POST", "/connexion", form, origin="https://127.0.0.1:8443").status, 303)
        self.assertEqual(self._request("POST", "/connexion", form, origin="null").status, 403)
        self.assertEqual(self._request("GET", "/static/admin.css").status, 200)
        self.assertEqual(self._request("GET", "/inconnu").status, 404)
        self.assertEqual(self._request("DELETE", "/").status, 405)
        failed = self._request("POST", "/connexion", b"identifiant=admin&mot_de_passe=faux")
        self.assertEqual(failed.status, 401)
        self.assertIn(b"incorrect", failed.body)

    def test_session_csrf_origin_mode_and_logout(self):
        token = self._login()
        home = self._request("GET", "/", cookie=token)
        self.assertEqual(home.status, 200)
        self.assertIn(b"Administration", home.body)
        csrf = home.body.split(b'name="csrf" value="')[1].split(b'"')[0].decode()
        self.assertEqual(self._request("POST", "/mode", b"mode=administration", cookie=token).status, 403)  # CSRF
        self.assertEqual(self._request("POST", "/mode", f"csrf={csrf}&mode=administration".encode(), cookie=token,
                                       origin="https://ailleurs.example").status, 403)  # autre origine
        self.assertEqual(dict(self._request("POST", "/mode", f"csrf={csrf}&mode=administration".encode(),
                                            cookie=token).headers)["Location"], "/")
        self.clock.value += REAUTH_SECONDS + 1
        self._request("POST", "/mode", f"csrf={csrf}&mode=tableau".encode(), cookie=token)
        again = self._request("POST", "/mode", f"csrf={csrf}&mode=administration".encode(), cookie=token)
        self.assertEqual(dict(again.headers)["Location"], "/reconnexion")
        logout = self._request("POST", "/deconnexion", f"csrf={csrf}".encode(), cookie=token)
        self.assertIn("Max-Age=0", dict(logout.headers)["Set-Cookie"])
        self.assertEqual(self._request("GET", "/", cookie=token).status, 303)


if __name__ == "__main__":
    unittest.main()
