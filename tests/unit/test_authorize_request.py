# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import base64
import unittest
from unittest.mock import patch

from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.domain.security.auth.authorize import authorize_request
from omega_serv.domain.security.auth.entities import AuthZone, UserAccount
from omega_serv.domain.security.auth.password_hashing import hash_password


def _basic_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def _zones():
    return (Zone("/private/", AuthZone(path_prefix="/private/", realm="Zone privee", allowed_users=("admin",))),)


def _users():
    return {"admin": UserAccount(username="admin", password_hash=hash_password("hunter2"))}


class TestAuthorizeRequest(unittest.TestCase):
    def test_path_outside_any_zone_is_not_protected(self):
        decision = authorize_request("/public/index.html", "GET", None, _zones(), _users())
        self.assertEqual(decision.outcome, "not_protected")

    def test_no_authorization_header_is_unauthenticated(self):
        decision = authorize_request("/private/doc.txt", "GET", None, _zones(), _users())
        self.assertEqual(decision.outcome, "unauthenticated")
        self.assertEqual(decision.realm, "Zone privee")

    def test_correct_credentials_allowed(self):
        header = _basic_header("admin", "hunter2")
        decision = authorize_request("/private/doc.txt", "GET", header, _zones(), _users())
        self.assertEqual(decision.outcome, "allowed")
        self.assertEqual(decision.username, "admin")

    def test_wrong_password_is_unauthenticated(self):
        header = _basic_header("admin", "wrong-password")
        decision = authorize_request("/private/doc.txt", "GET", header, _zones(), _users())
        self.assertEqual(decision.outcome, "unauthenticated")

    def test_unknown_username_is_unauthenticated(self):
        header = _basic_header("nobody", "whatever")
        decision = authorize_request("/private/doc.txt", "GET", header, _zones(), _users())
        self.assertEqual(decision.outcome, "unauthenticated")

    def test_correct_credentials_but_not_in_allowed_users_is_forbidden(self):
        zones = (Zone("/private/", AuthZone(path_prefix="/private/", realm="Zone", allowed_users=("someone-else",))),)
        header = _basic_header("admin", "hunter2")
        decision = authorize_request("/private/doc.txt", "GET", header, zones, _users())
        self.assertEqual(decision.outcome, "forbidden")

    def test_disallowed_method_is_forbidden_before_checking_credentials(self):
        zones = (Zone("/private/", AuthZone(path_prefix="/private/", realm="Zone", allowed_users=("admin",), allow_methods=("GET",))),)
        decision = authorize_request("/private/doc.txt", "POST", None, zones, _users())
        self.assertEqual(decision.outcome, "forbidden")

    def test_no_method_restriction_allows_any_method(self):
        header = _basic_header("admin", "hunter2")
        decision = authorize_request("/private/doc.txt", "DELETE", header, _zones(), _users())
        self.assertEqual(decision.outcome, "allowed")

    def test_longest_prefix_zone_wins(self):
        zones = (
            Zone("/private/", AuthZone(path_prefix="/private/", realm="Outer", allowed_users=("admin",))),
            Zone("/private/inner/", AuthZone(path_prefix="/private/inner/", realm="Inner", allowed_users=("inner-user",))),
        )
        decision = authorize_request("/private/inner/doc.txt", "GET", None, zones, _users())
        self.assertEqual(decision.realm, "Inner")

    def test_unknown_username_still_triggers_a_scrypt_computation(self):
        # Protection anti-enumeration : meme sans utilisateur trouve,
        # une verification de mot de passe doit etre executee (temps
        # constant) - on verifie que hashlib.scrypt est bien appele au
        # moins une fois, pas seulement que la reponse est correcte.
        with patch("omega_serv.domain.security.auth.password_hashing.hashlib.scrypt") as mock_scrypt:
            mock_scrypt.return_value = b"\x00" * 32
            header = _basic_header("nobody", "whatever")
            authorize_request("/private/doc.txt", "GET", header, _zones(), _users())
            self.assertTrue(mock_scrypt.called)


if __name__ == "__main__":
    unittest.main()
