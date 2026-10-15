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
import json
import shutil
import ssl
import tempfile
import time
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_zone import parse_proxy_zones
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
        port_a, _capture_a = await self._start_upstream(b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nA")
        port_b, _capture_b = await self._start_upstream(b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nB")
        await self._start_omega_serv(port_a, extra_upstream_ports=(port_b,))

        bodies = []
        for _ in range(4):
            _, _, data = await self._request("GET", "/api/users")
            bodies.append(data)

        self.assertEqual(bodies, [b"A", b"B", b"A", b"B"])

    async def test_native_load_polling_populates_health_state(self):
        """Phase 7 (§19.1) - bout en bout reel : un vrai socket TCP fait
        office de backend natif (repond toujours `{"cpu_percent": ..}`
        sur /.omega-serv-load/), le poller de fond interroge reellement
        ce socket (pas un double), et le score lisse/frais est
        exploitable via `ProxyHealthState` sans jamais passer par une
        requete client."""
        async def handle(reader, writer):
            await reader.read(4096)
            body = b'{"cpu_percent": 33.0}'
            writer.write(f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n".encode("latin-1") + body)
            await writer.drain()
            writer.close()

        fake = await asyncio.start_server(handle, "127.0.0.1", 0)
        self._upstream_servers.append(fake)
        upstream_port = fake.sockets[0].getsockname()[1]

        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/api/",
                    "upstreams": [{"host": "127.0.0.1", "port": upstream_port, "load_source": "native"}],
                    "load_balancing": "real_load",
                    "load_poll_interval_seconds": 0.05,
                    "load_poll_timeout_seconds": 2.0,
                }],
            }},
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        await asyncio.sleep(0.5)

        zone = parse_proxy_zones(config.options["reverse_proxy"].settings["zones"])[0]
        upstream = zone.upstreams[0]
        score = self.server._proxy_health_state.load_score_for(
            zone.url_prefix, upstream, max_age_seconds=60, now=time.monotonic(),
        )
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 33.0)

    async def test_active_health_check_runs_for_upstream_without_load_source(self):
        """§18.2 - bout en bout reel : un upstream SANS `load_source`
        (donc hors Phase 7) mais avec `active_health_check_enabled=True`
        recoit quand meme une tache de fond de polling (reouverture du
        §23 angle mort #7 "controle actif differe") - verifie qu'un
        backend qui echoue systematiquement a sa sonde active finit par
        passer DOWN, jamais seulement via le trafic client reel (controle
        PASSIF, deja teste ailleurs)."""
        async def handle(reader, writer):
            await reader.read(4096)
            writer.write(b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()

        fake = await asyncio.start_server(handle, "127.0.0.1", 0)
        self._upstream_servers.append(fake)
        upstream_port = fake.sockets[0].getsockname()[1]

        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/api/",
                    "upstreams": [{
                        "host": "127.0.0.1", "port": upstream_port,
                        "active_health_check_enabled": True, "active_health_check_path": "/healthz",
                    }],
                    "unhealthy_after": 2,
                    "load_poll_interval_seconds": 0.05,
                    "load_poll_timeout_seconds": 2.0,
                }],
            }},
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        await asyncio.sleep(0.5)

        zone = parse_proxy_zones(config.options["reverse_proxy"].settings["zones"])[0]
        upstream = zone.upstreams[0]
        self.assertEqual(self.server._proxy_health_state.status_for(zone.url_prefix, upstream), "down")
        self.assertIsNone(
            self.server._proxy_health_state.load_score_for(zone.url_prefix, upstream, max_age_seconds=60, now=time.monotonic())
        )

    async def test_backpressure_returns_503_when_upstream_is_saturated(self):
        """Phase 7bis (§20) - bout en bout reel : un vrai upstream lent
        (delai artificiel avant de repondre, pour creer une vraie
        fenetre de concurrence) avec `max_concurrent_requests: 1` - la
        2e requete CONCURRENTE recoit un vrai 503, jamais un 502."""
        release_event = asyncio.Event()

        async def handle(reader, writer):
            await reader.read(4096)
            await release_event.wait()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            await writer.drain()
            writer.close()

        slow_upstream = await asyncio.start_server(handle, "127.0.0.1", 0)
        self._upstream_servers.append(slow_upstream)
        upstream_port = slow_upstream.sockets[0].getsockname()[1]

        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/api/",
                    "upstreams": [{"host": "127.0.0.1", "port": upstream_port, "max_concurrent_requests": 1}],
                    "connect_timeout_seconds": 5,
                    "read_timeout_seconds": 5,
                }],
            }},
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        first = asyncio.create_task(asyncio.to_thread(self._request_sync, "GET", "/api/users"))
        await asyncio.sleep(0.2)  # laisse la 1ere requete occuper reellement le seul slot disponible
        second_status, _, _ = await self._request("GET", "/api/users")
        self.assertEqual(second_status, 503)

        release_event.set()
        first_status, _, _ = await first
        self.assertEqual(first_status, 200)

    async def test_cache_hit_never_touches_the_backend_again(self):
        """Phase 8 (§21) - bout en bout reel : le vrai `FilesystemProxyCacheStore`
        construit par `build_server()` (pas un double) ecrit reellement
        sur disque ; une 2e requete identique ne doit plus jamais
        atteindre le backend."""
        capture = {"count": 0}

        async def handle(reader, writer):
            await reader.read(4096)
            capture["count"] += 1
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nok")
            await writer.drain()
            writer.close()

        upstream = await asyncio.start_server(handle, "127.0.0.1", 0)
        self._upstream_servers.append(upstream)
        upstream_port = upstream.sockets[0].getsockname()[1]

        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/api/",
                    "upstreams": [{"host": "127.0.0.1", "port": upstream_port}],
                    "cache_enabled": True,
                }],
            }},
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        first_status, first_headers, first_body = await self._request("GET", "/api/users")
        second_status, second_headers, second_body = await self._request("GET", "/api/users")

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_headers.get("X-Omega-Cache"), "MISS")
        self.assertEqual(second_headers.get("X-Omega-Cache"), "HIT")
        self.assertEqual(first_body, second_body)
        self.assertEqual(capture["count"], 1)

        cache_dir = self.root / "var" / "cache" / "reverse_proxy"
        self.assertTrue(any(cache_dir.rglob("*.json")))

    async def test_admin_route_sets_and_reads_draining_through_the_real_server(self):
        """§22 reouverture - bout en bout reel : un vrai client HTTP
        (depuis une IP de confiance) pilote `/.omega-serv-admin/health`
        d'un vrai serveur en cours d'execution, jamais seulement
        `handle_admin_request` appelee directement en memoire."""
        upstream = await asyncio.start_server(
            lambda r, w: w.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"), "127.0.0.1", 0,
        )
        self._upstream_servers.append(upstream)
        upstream_port = upstream.sockets[0].getsockname()[1]

        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "security": {"allowed_methods": ["GET", "HEAD", "POST"]},
            "options": {
                "reverse_proxy": {
                    "enabled": True,
                    "zones": [{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": upstream_port}]}],
                },
                "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"]},
            },
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        status, _, body = await self._request("GET", "/.omega-serv-admin/health?zone=/api/")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["upstreams"], {f"127.0.0.1:{upstream_port}": "up"})

        status, _, body = await self._request(
            "POST", f"/.omega-serv-admin/health?zone=/api/&upstream=127.0.0.1:{upstream_port}&status=draining",
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "draining")

        status, _, body = await self._request("GET", "/.omega-serv-admin/health?zone=/api/")
        self.assertEqual(json.loads(body)["upstreams"], {f"127.0.0.1:{upstream_port}": "draining"})

    async def test_admin_route_refuses_from_an_untrusted_network(self):
        """§19.1 meme garde reutilisee : sans `trusted_proxy` actif,
        meme une requete venue de 127.0.0.1 est refusee (fail-CLOSED,
        jamais un repli 'localhost toujours autorise')."""
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"reverse_proxy": {"enabled": True, "zones": []}},
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        status, _, _ = await self._request("GET", "/.omega-serv-admin/health?zone=/api/")
        self.assertEqual(status, 403)

    async def test_admin_cache_stats_reflect_real_traffic_through_the_server(self):
        upstream = await asyncio.start_server(
            lambda r, w: w.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"), "127.0.0.1", 0,
        )
        self._upstream_servers.append(upstream)
        upstream_port = upstream.sockets[0].getsockname()[1]

        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {
                "reverse_proxy": {
                    "enabled": True,
                    "zones": [{
                        "url_prefix": "/api/", "cache_enabled": True,
                        "upstreams": [{"host": "127.0.0.1", "port": upstream_port}],
                    }],
                },
                "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"]},
            },
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

        await self._request("GET", "/api/users")
        await self._request("GET", "/api/users")

        status, _, body = await self._request("GET", "/.omega-serv-admin/cache-stats?zone=/api/")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"zone": "/api/", "hits": 1, "misses": 1})


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
        await self._start_omega_serv(verify_upstream_tls=False)
        status, data = await asyncio.to_thread(self._request_sync)
        self.assertEqual(status, 200)
        self.assertEqual(data, b"https-ok")

    async def test_https_upstream_rejected_when_verification_enabled(self):
        await self._start_omega_serv(verify_upstream_tls=True)
        status, _data = await asyncio.to_thread(self._request_sync)
        self.assertEqual(status, 502)


if __name__ == "__main__":
    unittest.main()
