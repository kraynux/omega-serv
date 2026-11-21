# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Certificats locaux et echeances (etude modules du panneau web, module 3 ; cadre de l'auteur du 2026-11-17 : aucun
risque, aucune connexion) : sources, etats, cles jamais lues, openssl absent, vue web."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.certificate_watch import CertificateWatch
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.application.tls.certificate_inventory import (
    CertificateLine,
    certificate_sources,
    inspect_all,
    state_text,
)
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.domain.security.tls.entities import CertificateInfo
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
PEM = b"-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"


class _Tool:
    def __init__(self, days: dict[str, int]):
        self.days, self.read = days, []

    def inspect_certificate(self, path):
        self.read.append(path.name)
        if path.name not in self.days:
            raise RuntimeError("abime")
        return CertificateInfo("CN=x", "CN=ca", NOW - timedelta(days=90), NOW + timedelta(days=self.days[path.name]),
                               san_dns=("exemple.org",))


class TestInventory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.fs = LocalFilesystem()
        certs = self.root / "secure" / "certificates"
        (certs / "server").mkdir(parents=True)
        (certs / "admin").mkdir()
        (certs / "ca").mkdir()
        (certs / "server" / "server.pem").write_bytes(PEM)
        (certs / "server" / "server.key").write_text("-----BEGIN PRIVATE KEY-----\nsecret\n")
        (certs / "admin" / "admin.pem").write_bytes(PEM)
        (certs / "ca" / "ca.crt").write_bytes(PEM)
        (certs / "ca" / "ca-key.pem").write_text("-----BEGIN PRIVATE KEY-----\nsecret\n")  # cle en .pem
        (certs / "ca" / "ancien.pem.old").write_bytes(PEM)
        (certs / "ca" / "abime.pem").write_bytes(PEM)

    def _lines(self, tool):
        sources = certificate_sources(OmegaServConfig(), self.root, self.fs, Path("secure/certificates/admin/admin.pem"))
        return inspect_all(sources, self.root, self.fs, (lambda: tool) if tool else None, NOW)

    def test_sources_states_and_keys_never_read(self):
        tool = _Tool({"server.pem": 200, "admin.pem": 20, "ca.crt": 3})
        lines = {line.path: line for line in self._lines(tool)}
        self.assertEqual(lines["secure/certificates/server/server.pem"].label, "Site")
        self.assertEqual(lines["secure/certificates/server/server.pem"].state, "ok")
        self.assertEqual(lines["secure/certificates/admin/admin.pem"].label, "Panneau web")
        self.assertEqual(lines["secure/certificates/admin/admin.pem"].state, "soon")
        self.assertEqual(lines["secure/certificates/ca/ca.crt"].state, "urgent")
        self.assertEqual(lines["secure/certificates/ca/abime.pem"].state, "unreadable")
        self.assertEqual(len(lines), 4)  # site et panneau une seule fois ; cles, .old ignores
        self.assertNotIn("ca-key.pem", tool.read)  # une cle n'est jamais passee a openssl
        self.assertEqual(lines["secure/certificates/server/server.pem"].names, ("exemple.org",))
        self.assertEqual(lines["secure/certificates/ca/ca.crt"].not_after, "2026-11-20")

    def test_expired_missing_unreadable_and_no_openssl(self):
        expired = self._lines(_Tool({"server.pem": -4, "admin.pem": 1, "ca.crt": 1}))[0]
        self.assertEqual((expired.state, state_text(expired)), ("expired", "expiré depuis 4 jours"))
        (self.root / "secure/certificates/admin/admin.pem").unlink()
        os.chmod(self.root / "secure/certificates/ca/ca.crt", 0)
        try:
            lines = {line.path: line for line in self._lines(None)}
        finally:
            os.chmod(self.root / "secure/certificates/ca/ca.crt", 0o600)
        self.assertEqual(lines["secure/certificates/admin/admin.pem"].state, "missing")
        if os.geteuid() != 0:
            self.assertEqual(lines["secure/certificates/ca/ca.crt"].state, "unreadable")
        self.assertEqual(lines["secure/certificates/server/server.pem"].state, "no_tool")
        self.assertEqual(CertificateLine.from_dict(lines["secure/certificates/server/server.pem"].to_dict()),
                         lines["secure/certificates/server/server.pem"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl absent")
    def test_real_openssl_certificate(self):
        from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
        from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool
        target = self.root / "secure/certificates/server"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "5", "-subj", "/CN=essai",
                        "-keyout", str(target / "server.key"), "-out", str(target / "server.pem")],
                       check=True, capture_output=True)
        sources = [("Site", target / "server.pem")]
        (line,) = inspect_all(sources, self.root, self.fs, lambda: OpensslCertificateTool(SubprocessRunner()),
                              datetime.now(timezone.utc))
        self.assertEqual(line.state, "urgent")
        self.assertIn(line.days, (4, 5))


class TestWebView(unittest.TestCase):
    def test_certificates_view_lists_lines_for_every_role(self):
        accounts = (AdminAccount("lecteur", hash_password("mot-de-passe-1"), "lecture"),)
        auth = AdminAuth(lambda: accounts, lambda: 1.7e9, lambda line: None, local_only=True,
                         used_backup_codes=set, mark_backup_code_used=lambda code: None)
        watch = CertificateWatch(lambda: [CertificateLine("Site", "secure/x.pem", "soon", 12, "2026-11-29",
                                                          names=("exemple.org",))])
        asyncio.run(watch.refresh())
        app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",)), auth, "prod", certificates=watch)

        def request(method, target, body=b"", cookie=""):
            headers = (("Host", "127.0.0.1:9643"), ("Cookie", cookie))
            return asyncio.run(app.handle(AdminRequest("127.0.0.1", method, target, headers, body)))
        body = urlencode({"identifiant": "lecteur", "mot_de_passe": "mot-de-passe-1"}).encode()
        token = dict(request("POST", "/connexion", body).headers)["Set-Cookie"].split(";")[0].split("=", 1)[1]
        page = request("GET", "/certificats", cookie=f"{COOKIE_NAME}={token}").body.decode()
        self.assertIn('href="/certificats"', page)
        self.assertIn("secure/x.pem", page)
        self.assertIn("expire dans 12 jours", page)
        self.assertIn('class="tone-warn"', page)
        self.assertEqual(request("GET", "/certificats").status, 303)  # connexion exigee


if __name__ == "__main__":
    unittest.main()
