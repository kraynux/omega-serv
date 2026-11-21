"""Tableau de bord web, lot 2 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md, decisions de l'auteur du 2026-11-16) :
reglages de l'option `admin_web`, avertissements (jamais un refus de demarrer le site), reponses du processus."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.checks import (
    admin_web_certificate_paths,
    admin_web_settings,
    admin_web_warnings,
)
from omega_serv.application.admin_web.responses import security_headers
from omega_serv.application.admin_web.web_app import AdminRequest, AdminWebApp
from omega_serv.bootstrap.early_language import is_admin_web_process
from omega_serv.domain.admin_web.settings import (
    DEFAULT_ALLOWED_NETWORKS,
    AdminWebSettings,
    validate_admin_web,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import validate_config
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


def _config(admin: dict | None, port: int = 8080) -> OmegaServConfig:
    options = {} if admin is None else {"admin_web": {"enabled": True, **admin}}
    return OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": port}, "options": options})


def _errors(**admin) -> list[str]:
    return validate_admin_web(AdminWebSettings.from_settings(admin), server_bind="0.0.0.0", server_port=8080)


class TestSettings(unittest.TestCase):
    def test_safe_defaults(self):
        settings = AdminWebSettings.from_settings({})
        self.assertEqual((settings.bind, settings.port, settings.tls), ("127.0.0.1", 9643, "none"))
        self.assertTrue(settings.local_only)
        self.assertEqual(settings.url, "http://127.0.0.1:9643/")
        self.assertIn("100.64.0.0/10", settings.allowed_networks)   # Tailscale
        self.assertIn("192.168.0.0/16", settings.allowed_networks)  # LAN (Q6)
        self.assertEqual(_errors(), [])

    def test_tls_required_outside_loopback(self):
        self.assertTrue(any("TLS est obligatoire" in e for e in _errors(bind="192.168.1.10", tls="none")))
        self.assertEqual(_errors(bind="192.168.1.10", tls="site"), [])
        self.assertEqual(AdminWebSettings.from_settings({"bind": "::1", "tls": "own"}).url, "https://[::1]:9643/")

    def test_bad_values_are_refused_never_converted(self):
        self.assertTrue(_errors(port="8443"))
        self.assertTrue(_errors(port=0))
        self.assertTrue(_errors(port=True))
        self.assertTrue(_errors(bind="mon-serveur"))
        self.assertTrue(_errors(tls="oui"))
        self.assertTrue(_errors(allowed_networks=[]))
        self.assertTrue(_errors(allowed_networks=["10.0.0.0/33"]))
        self.assertTrue(_errors(tls="own", certificate_path=""))

    def test_never_the_site_port(self):
        self.assertTrue(any("celui du site" in e for e in _errors(port=8080)))
        self.assertTrue(any("celui du site" in e for e in _errors(port=8080, bind="127.0.0.1")))  # site sur 0.0.0.0
        self.assertEqual(validate_admin_web(AdminWebSettings.from_settings({"port": 8080}), server_bind="192.168.1.2",
                                            server_port=8080), [])  # adresses differentes : pas de conflit

    def test_only_checked_when_enabled(self):
        self.assertEqual(validate_config(OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 8080},
                                                                    "options": {"admin_web": {"enabled": False,
                                                                                              "port": "x"}}})), [])
        self.assertTrue(any("admin_web" in e for e in validate_config(_config({"port": "x"}))))
        self.assertIsNone(admin_web_settings(_config(None)))


class TestWarnings(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.fs = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_certificate_is_a_warning(self):
        config = _config({"tls": "own"})
        self.assertEqual(admin_web_certificate_paths(config, admin_web_settings(config)),
                         ("secure/certificates/admin/admin.pem", "secure/certificates/admin/admin.key"))
        self.assertEqual(len(admin_web_warnings(config, self.fs, self.root)), 2)
        folder = self.root / "secure" / "certificates" / "admin"
        folder.mkdir(parents=True)
        (folder / "admin.pem").write_text("x")
        (folder / "admin.key").write_text("x")
        self.assertEqual(admin_web_warnings(config, self.fs, self.root), [])
        self.assertEqual(admin_web_warnings(_config({"tls": "none"}), self.fs, self.root), [])
        site = _config({"tls": "site"})
        self.assertEqual(admin_web_certificate_paths(site, admin_web_settings(site))[0], site.tls.certificate_path)

    def test_port_of_another_instance(self):
        other = InstanceEntry("autre", self.root / "autre", "127.0.0.1", 9000, "", datetime.now(timezone.utc))
        site_clash = admin_web_warnings(_config({"port": 9000}), self.fs, self.root, [(other, None)])
        self.assertTrue(any("site de l'instance 'autre'" in w for w in site_clash))
        admin_clash = admin_web_warnings(_config({"port": 8443}), self.fs, self.root, [(other, 8443)])
        self.assertTrue(any("administration web de l'instance 'autre'" in w for w in admin_clash))
        self.assertEqual(admin_web_warnings(_config({"port": 8444}), self.fs, self.root, [(other, 8443)]), [])


class TestResponses(unittest.TestCase):
    def test_security_headers_and_network_first(self):
        names = {name for name, _value in security_headers(tls=False)}
        self.assertTrue({"Content-Security-Policy", "X-Frame-Options", "Cache-Control", "Referrer-Policy"} <= names)
        self.assertNotIn("Strict-Transport-Security", names)
        self.assertIn("Strict-Transport-Security", {n for n, _v in security_headers(tls=True)})
        auth = AdminAuth(lambda: (), lambda: 0.0, lambda message: None, local_only=True,
                         used_backup_codes=set, mark_backup_code_used=lambda code: None)
        app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",)), auth, "prod")
        refused = asyncio.run(app.handle(AdminRequest("203.0.113.9", "POST", "/connexion", (), b"")))
        self.assertEqual(refused.status, 403)  # le reseau d'abord, avant toute autre regle
        self.assertEqual(asyncio.run(app.handle(AdminRequest("::ffff:127.0.0.1", "GET", "/connexion", (), b""))).status,
                         200)
        self.assertEqual(len(DEFAULT_ALLOWED_NETWORKS), 8)

    def test_admin_web_process_is_recognised_for_its_language(self):
        self.assertTrue(is_admin_web_process(["admin-web", "run"]))
        self.assertTrue(is_admin_web_process(["--config", "config/omega-serve.json", "admin-web", "run"]))
        self.assertFalse(is_admin_web_process(["serve"]))
        self.assertFalse(is_admin_web_process(["riposte", "run"]))


if __name__ == "__main__":
    unittest.main()
