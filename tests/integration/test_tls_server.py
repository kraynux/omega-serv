"""Tests d'integration Phase 6 (TLS direct minimal, 6a) : vrai handshake
TLS contre un serveur reel, vrai certificat auto-signe genere via
openssl reel - aucun mock, meme discipline que test_waf_server.py."""
import asyncio
import shutil
import ssl
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.tls.entities import CaParams, CsrParams, SelfSignedCertParams
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

_OPENSSL_MISSING = shutil.which("openssl") is None


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestTlsServerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello tls")

        self.key_path = self.root / "secure" / "certificates" / "server" / "server.key"
        self.cert_path = self.root / "secure" / "certificates" / "server" / "server.pem"
        tool = OpensslCertificateTool(SubprocessRunner())
        params = SelfSignedCertParams(common_name="localhost", san_dns=("localhost",), san_ip=("127.0.0.1",))
        tool.generate_self_signed(params, self.key_path, self.cert_path)

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def _start(self, **security_overrides):
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "security": {"hsts_enabled": False, **security_overrides},
            "tls": {
                "enabled": True, "mode": "direct",
                "certificate": {
                    "certificate_path": "secure/certificates/server/server.pem",
                    "private_key_path": "secure/certificates/server/server.key",
                },
            },
        })
        self.server = build_server(self.config, self.root, self.filesystem, self.logger, SystemClock())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    def _client_ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=str(self.cert_path))
        context.check_hostname = False
        return context

    def _https_get_sync(self, path: str) -> tuple[int, dict]:
        import http.client
        conn = http.client.HTTPSConnection("127.0.0.1", self.port, timeout=3, context=self._client_ssl_context())
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            resp.read()
            return resp.status, dict(resp.getheaders())
        finally:
            conn.close()

    async def _https_get(self, path: str):
        return await asyncio.to_thread(self._https_get_sync, path)

    async def test_real_tls_handshake_serves_content(self):
        await self._start()
        status, _ = await self._https_get("/index.html")
        self.assertEqual(status, 200)

    async def test_hsts_header_present_when_enabled(self):
        await self._start(hsts_enabled=True, hsts_max_age=3600)
        status, headers = await self._https_get("/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Strict-Transport-Security"), "max-age=3600; includeSubDomains")

    async def test_hsts_header_absent_when_disabled(self):
        await self._start(hsts_enabled=False)
        _, headers = await self._https_get("/index.html")
        self.assertNotIn("Strict-Transport-Security", headers)


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestTlsServerCaLocaleIntegration(unittest.IsolatedAsyncioTestCase):
    """CA locale (6b) : le client ne fait confiance qu'a la CA (jamais
    directement au certificat serveur, contrairement aux tests
    auto-signes ci-dessus) - preuve que la chaine complete fonctionne
    reellement, pas seulement que le certificat serveur est valide."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello ca locale")

        tool = OpensslCertificateTool(SubprocessRunner())
        ca_dir = self.root / "secure" / "certificates" / "ca"
        self.ca_cert_path = ca_dir / "root-ca.pem"
        ca_key_path = ca_dir / "root-ca.key"
        serial_path = ca_dir / "serial.txt"
        index_path = ca_dir / "index.txt"
        tool.generate_ca(CaParams(common_name="Test CA", key_password="capass123"), ca_key_path, self.ca_cert_path, serial_path, index_path)

        server_dir = self.root / "secure" / "certificates" / "server"
        server_key_path = server_dir / "server.key"
        server_csr_path = server_dir / "server.csr"
        tool.generate_csr(
            CsrParams(common_name="localhost", san_dns=("localhost",), san_ip=("127.0.0.1",)),
            server_key_path, server_csr_path,
        )
        self.server_cert_path = server_dir / "server.pem"
        tool.sign_csr(server_csr_path, ca_key_path, self.ca_cert_path, "capass123", serial_path, index_path, 365, self.server_cert_path)
        self.fullchain_path = server_dir / "fullchain.pem"
        tool.build_fullchain(self.server_cert_path, self.ca_cert_path, self.fullchain_path)
        self.key_path = server_key_path

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def test_client_trusting_only_ca_completes_handshake_via_fullchain(self):
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "security": {"hsts_enabled": False},
            "tls": {
                "enabled": True, "mode": "direct",
                "certificate": {
                    "certificate_path": "secure/certificates/server/fullchain.pem",
                    "private_key_path": "secure/certificates/server/server.key",
                },
            },
        })
        self.server = build_server(config, self.root, self.filesystem, self.logger, SystemClock())
        await self.server.start()
        port = self.server.sockets[0].getsockname()[1]

        context = ssl.create_default_context(cafile=str(self.ca_cert_path))
        context.check_hostname = False

        def _get() -> int:
            import http.client
            conn = http.client.HTTPSConnection("127.0.0.1", port, timeout=3, context=context)
            try:
                conn.request("GET", "/index.html")
                resp = conn.getresponse()
                resp.read()
                return resp.status
            finally:
                conn.close()

        status = await asyncio.to_thread(_get)
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
