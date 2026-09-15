# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration du reverse proxy sortant (OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md, phases 2-3 : un ou plusieurs upstreams HTTP/HTTPS
avec repartition de charge round-robin, sans WebSocket) : serveur
OMEGA-SERV reel, connexions TCP reelles, et un ou plusieurs vrais faux
backends HTTP (vrais sockets TCP, vrai protocole sur le fil) qui
tiennent lieu d'upstreams - meme discipline que test_fastcgi_server.py,
aucun mock du transport.

TestReverseProxyTlsUpstreamIntegration (phase 3, §5.3/§12) : meme
discipline etendue a un vrai handshake TLS de bout en bout - un vrai
certificat auto-signe genere via openssl reel pour le faux upstream
HTTPS."""
import asyncio
import http.client
import shutil
import ssl
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

_OPENSSL_MISSING = shutil.which("openssl") is None


async def _fake_upstream(raw_response: bytes, capture: dict) -> asyncio.AbstractServer:
    async def handle(reader, writer):
        data = await reader.read(4096)
        capture["received"] = data
        writer.write(raw_response)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server


class TestReverseProxyServerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("static ok")
        self._upstream_servers: list[asyncio.AbstractServer] = []

    async def asyncTearDown(self):
        for server in self._upstream_servers:
            server.close()
            await server.wait_closed()
        await self.server.close()
        self._tmp.cleanup()

    async def _start_upstream(self, raw_response: bytes) -> tuple[int, dict]:
        capture: dict = {}
        server = await _fake_upstream(raw_response, capture)
        self._upstream_servers.append(server)
        return server.sockets[0].getsockname()[1], capture

    async def _start_omega_serv(self, upstream_port: int, extra_upstream_ports: tuple[int, ...] = ()) -> None:
        upstream_ports = (upstream_port, *extra_upstream_ports)
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "security": {"allowed_methods": ["GET", "HEAD", "POST"]},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/api/",
                    "upstreams": [{"host": "127.0.0.1", "port": p} for p in upstream_ports],
                    "connect_timeout_seconds": 2,
                    "read_timeout_seconds": 2,
                }],
            }},
        })
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    def _request_sync(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, dict(resp.getheaders()), data
        finally:
            conn.close()

    async def _request(self, method, path, body=None, headers=None):
        return await asyncio.to_thread(self._request_sync, method, path, body, headers)

    async def test_response_relayed_through_full_stack(self):
        upstream_port, _capture = await self._start_upstream(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 13\r\n\r\n{\"ok\": true}\n"
        )
        await self._start_omega_serv(upstream_port)
        status, headers, data = await self._request("GET", "/api/users")
        self.assertEqual(status, 200)
        self.assertEqual(data, b'{"ok": true}\n')
        self.assertEqual(headers.get("Content-Type"), "application/json")

    async def test_static_files_still_served_outside_proxy_prefix(self):
        upstream_port, _capture = await self._start_upstream(b"HTTP/1.1 200 OK\r\n\r\n")
        await self._start_omega_serv(upstream_port)
        status, _, data = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"static ok")

    async def test_x_forwarded_for_set_to_real_client_ip(self):
        upstream_port, capture = await self._start_upstream(b"HTTP/1.1 200 OK\r\n\r\n")
        await self._start_omega_serv(upstream_port)
        await self._request("GET", "/api/users")
        sent = capture["received"].decode("latin-1")
        self.assertIn("X-Forwarded-For: 127.0.0.1\r\n", sent)

    async def test_host_header_replaced_with_upstream_by_default(self):
        upstream_port, capture = await self._start_upstream(b"HTTP/1.1 200 OK\r\n\r\n")
        await self._start_omega_serv(upstream_port)
        await self._request("GET", "/api/users")
        sent = capture["received"].decode("latin-1")
        self.assertIn(f"Host: 127.0.0.1:{upstream_port}\r\n", sent)

    async def test_security_headers_still_applied_to_proxied_response(self):
        upstream_port, _capture = await self._start_upstream(b"HTTP/1.1 200 OK\r\n\r\n")
        await self._start_omega_serv(upstream_port)
        _, headers, _ = await self._request("GET", "/api/users")
        self.assertIn("X-Content-Type-Options", headers)
        self.assertIn("Content-Security-Policy", headers)

    async def test_unreachable_upstream_returns_bad_gateway(self):
        # Port jamais ouvert (serveur ferme immediatement) - upstream
        # indisponible reel, pas simule.
        dead_server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        dead_port = dead_server.sockets[0].getsockname()[1]
        dead_server.close()
        await dead_server.wait_closed()

        await self._start_omega_serv(dead_port)
        status, _, _ = await self._request("GET", "/api/users")
        self.assertEqual(status, 502)

    async def test_post_body_forwarded_to_upstream(self):
        upstream_port, capture = await self._start_upstream(b"HTTP/1.1 200 OK\r\n\r\n")
        await self._start_omega_serv(upstream_port)
        await self._request("POST", "/api/submit", body=b"field=value")
        sent = capture["received"].decode("latin-1")
        self.assertTrue(sent.endswith("field=value"))

    async def test_round_robin_alternates_between_real_upstreams(self):
        # Phase 2 (repartition de charge) : verification avec DEUX
        # vrais faux backends TCP distincts - jamais un simple double
        # d'objet Python, la rotation doit etre observable sur le fil
        # reel (l'un des deux ports recevant chaque requete tour a
        # tour).
        port_a, _capture_a = await self._start_upstream(b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nA")
        port_b, _capture_b = await self._start_upstream(b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nB")
        await self._start_omega_serv(port_a, extra_upstream_ports=(port_b,))

        bodies = []
        for _ in range(4):
            _, _, data = await self._request("GET", "/api/users")
            bodies.append(data)

        self.assertEqual(bodies, [b"A", b"B", b"A", b"B"])


async def _fake_https_upstream(raw_response: bytes, ssl_context: ssl.SSLContext) -> asyncio.AbstractServer:
    async def handle(reader, writer):
        await reader.read(4096)
        writer.write(raw_response)
        await writer.drain()
        writer.close()

    return await asyncio.start_server(handle, "127.0.0.1", 0, ssl=ssl_context)


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestReverseProxyTlsUpstreamIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()

        key_path = self.root / "upstream.key"
        cert_path = self.root / "upstream.pem"
        tool = OpensslCertificateTool(SubprocessRunner())
        tool.generate_self_signed(
            SelfSignedCertParams(common_name="localhost", san_dns=("localhost",), san_ip=("127.0.0.1",)),
            key_path, cert_path,
        )
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        self.upstream = await _fake_https_upstream(
            b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\n\r\nhttps-ok", server_context,
        )
        self.upstream_port = self.upstream.sockets[0].getsockname()[1]

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()

    async def asyncTearDown(self):
        self.upstream.close()
        await self.upstream.wait_closed()
        await self.server.close()
        self._tmp.cleanup()

    async def _start_omega_serv(self, verify_upstream_tls: bool) -> None:
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/api/",
                    "upstreams": [{"host": "127.0.0.1", "port": self.upstream_port, "use_tls": True}],
                    "connect_timeout_seconds": 2, "read_timeout_seconds": 2,
                    "verify_upstream_tls": verify_upstream_tls,
                }],
            }},
        })
        self.server = build_server(config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    def _request_sync(self) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("GET", "/api/users")
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    async def test_https_upstream_reached_when_verification_disabled(self):
        # Certificat auto-signe, jamais dans le magasin de confiance
        # systeme - la seule maniere reelle de completer ce handshake
        # est verify_upstream_tls=False, exactement comme documente
        # (§5.3, dangereux mais explicite).
        await self._start_omega_serv(verify_upstream_tls=False)
        status, data = await asyncio.to_thread(self._request_sync)
        self.assertEqual(status, 200)
        self.assertEqual(data, b"https-ok")

    async def test_https_upstream_rejected_when_verification_enabled(self):
        # Comportement par defaut (verify_upstream_tls=True) : la
        # verification stricte echoue reellement contre ce certificat
        # auto-signe non reconnu - releve en 502, jamais une reussite
        # accidentelle.
        await self._start_omega_serv(verify_upstream_tls=True)
        status, _data = await asyncio.to_thread(self._request_sync)
        self.assertEqual(status, 502)


if __name__ == "__main__":
    unittest.main()
