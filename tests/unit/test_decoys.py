# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""plan_active_defense_omega_serv.md, Phase 3 - fixture `fake_admin`,
registre et dispatcher Niveau 1 (in-process)."""
import json
import unittest

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.security.active_defense.value_objects import KNOWN_FIXTURE_PROFILE_NAMES
from omega_serv.infrastructure.decoys.fake_admin_handler import handle_fake_admin
from omega_serv.infrastructure.decoys.fake_api_handler import handle_fake_api
from omega_serv.infrastructure.decoys.fake_cms_handler import handle_fake_cms
from omega_serv.infrastructure.decoys.fake_secrets_handler import handle_fake_secrets
from omega_serv.infrastructure.decoys.in_process_fixture_dispatcher import (
    InProcessFixtureDispatcher,
)
from omega_serv.infrastructure.decoys.registry import FIXTURE_HANDLERS


def _request(method: str = "GET", body: bytes | None = None, path: str = "/admin") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method=method,
        path=path, raw_path=path, query="", headers=HttpHeaders.from_pairs([]),
        body=body, content_length=None, is_tls=False,
    )


class TestHandleFakeAdmin(unittest.TestCase):
    def test_get_returns_the_login_form_without_error_message(self):
        response = handle_fake_admin(_request())
        self.assertEqual(response.status, HttpStatus.OK)
        body = response.body.decode("utf-8")
        self.assertIn("Connexion administrateur", body)
        self.assertNotIn("Identifiants invalides", body)

    def test_post_returns_a_generic_failure_message(self):
        response = handle_fake_admin(_request(method="POST", body=b"username=admin&password=whatever"))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertIn("Identifiants invalides", response.body.decode("utf-8"))

    def test_post_never_reflects_submitted_credentials(self):
        response = handle_fake_admin(_request(method="POST", body=b"username=' OR 1=1 --&password=x"))
        self.assertNotIn("OR 1=1", response.body.decode("utf-8"))

    def test_sets_content_length_matching_the_body(self):
        response = handle_fake_admin(_request())
        self.assertEqual(response.headers.get("Content-Length"), str(len(response.body)))


class TestHandleFakeCms(unittest.TestCase):
    def test_get_login_returns_a_login_page(self):
        response = handle_fake_cms(_request(path="/wp-login.php"))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertIn("Connexion", response.body.decode("utf-8"))

    def test_post_login_returns_a_generic_failure_message(self):
        response = handle_fake_cms(_request(method="POST", path="/wp-login.php", body=b"log=admin&pwd=x"))
        self.assertIn("Identifiants invalides", response.body.decode("utf-8"))

    def test_wp_admin_returns_a_fake_dashboard(self):
        response = handle_fake_cms(_request(path="/wp-admin"))
        self.assertIn("Tableau de bord", response.body.decode("utf-8"))

    def test_never_reflects_submitted_credentials(self):
        response = handle_fake_cms(_request(method="POST", path="/wp-login.php", body=b"log=' OR 1=1 --"))
        self.assertNotIn("OR 1=1", response.body.decode("utf-8"))


class TestHandleFakeApi(unittest.TestCase):
    def test_health_path_returns_ok_json(self):
        response = handle_fake_api(_request(path="/api/v1/health"))
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(json.loads(response.body)["status"], "ok")

    def test_post_returns_unauthorized(self):
        response = handle_fake_api(_request(method="POST", path="/api/v1/users", body=b'{"token":"x"}'))
        self.assertEqual(response.status, HttpStatus.UNAUTHORIZED)

    def test_never_reflects_submitted_body(self):
        response = handle_fake_api(_request(method="POST", path="/api/v1/users", body=b"'; DROP TABLE users; --"))
        self.assertNotIn("DROP TABLE", response.body.decode("utf-8"))

    def test_unknown_path_returns_not_found_payload(self):
        response = handle_fake_api(_request(path="/api/v1/whatever"))
        self.assertEqual(json.loads(response.body)["error"], "not_found")


class TestHandleFakeSecrets(unittest.TestCase):
    def test_returns_a_plausible_but_fake_env_file(self):
        response = handle_fake_secrets(_request(path="/.env"))
        self.assertEqual(response.status, HttpStatus.OK)
        body = response.body.decode("utf-8")
        self.assertIn("DB_PASSWORD=change-me", body)

    def test_same_fixed_content_regardless_of_the_exact_path_scanned(self):
        first = handle_fake_secrets(_request(path="/config.php.bak"))
        second = handle_fake_secrets(_request(path="/backup.sql"))
        self.assertEqual(first.body, second.body)


class TestFixtureRegistry(unittest.TestCase):
    def test_fake_admin_is_registered(self):
        self.assertIn("fake_admin", FIXTURE_HANDLERS)
        self.assertIs(FIXTURE_HANDLERS["fake_admin"], handle_fake_admin)

    def test_fake_cms_api_secrets_are_registered(self):
        self.assertIs(FIXTURE_HANDLERS["fake_cms"], handle_fake_cms)
        self.assertIs(FIXTURE_HANDLERS["fake_api"], handle_fake_api)
        self.assertIs(FIXTURE_HANDLERS["fake_secrets"], handle_fake_secrets)

    def test_stays_synchronized_with_the_domain_validation_constant(self):
        # domain/security/active_defense/value_objects.py::KNOWN_FIXTURE_PROFILE_NAMES
        # duplique volontairement ces cles (domain ne peut jamais
        # importer infrastructure) - ce test est le seul garde-fou
        # anti-derive entre les deux (guide d'aide, Active Defense - Reglages).
        self.assertEqual(set(FIXTURE_HANDLERS), KNOWN_FIXTURE_PROFILE_NAMES)


class TestInProcessFixtureDispatcher(unittest.TestCase):
    def test_known_profile_renders_a_response(self):
        dispatcher = InProcessFixtureDispatcher()
        response = dispatcher.render("fake_admin", _request())
        assert response is not None
        self.assertEqual(response.status, HttpStatus.OK)

    def test_unknown_profile_returns_none(self):
        dispatcher = InProcessFixtureDispatcher()
        self.assertIsNone(dispatcher.render("does-not-exist", _request()))


if __name__ == "__main__":
    unittest.main()
