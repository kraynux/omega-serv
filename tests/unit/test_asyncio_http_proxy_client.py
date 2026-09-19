"""Teste l'implementation asyncio reelle contre un faux serveur HTTP
(vrai socket TCP, vrais octets sur le fil) - meme discipline que
test_asyncio_fastcgi_client.py (I/O reelle, pas de mock du transport).

TestAsyncioHttpProxyClientTls (phase 3, §5.3/§12) : meme discipline
etendue a un vrai handshake TLS - un vrai certificat auto-signe genere
via openssl reel (meme patron que test_openssl_certificate_tool.py/
test_tls_server.py), jamais un contexte SSL invente a la main."""
import asyncio
import shutil
import ssl
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.proxy.asyncio_http_proxy_client import AsyncioHttpProxyClient
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool
from omega_serv.infrastructure.tls.ssl_context_builder import build_client_ssl_context
from omega_serv.ports.http_proxy_client_port import HttpProxyConnectionError

_OPENSSL_MISSING = shutil.which("openssl") is None


async def _serve_one_response(raw_response: bytes) -> tuple[asyncio.AbstractServer, int, bytearray]:
    received = bytearray()

    async def handle(reader, writer):
        data = await reader.read(4096)
        received.extend(data)
        writer.write(raw_response)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port, received


class TestAsyncioHttpProxyClient(unittest.IsolatedAsyncioTestCase):
    async def test_parses_status_headers_and_body(self):
        server, port, _received = await _serve_one_response(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 5\r\n\r\nhello"
        )
        try:
            client = AsyncioHttpProxyClient()
            result = await client.forward_request(
                "127.0.0.1", port, "GET", "/index.html", (("Host", "127.0.0.1"),), b"", 2.0, 2.0,
            )
            self.assertEqual(result.status_code, 200)
            self.assertEqual(dict(result.headers)["Content-Type"], "text/plain")
            self.assertEqual(result.body, b"hello")
        finally:
            server.close()
            await server.wait_closed()

    async def test_request_line_and_headers_sent_correctly(self):
        server, port, received = await _serve_one_response(b"HTTP/1.1 204 No Content\r\n\r\n")
        try:
            client = AsyncioHttpProxyClient()
            await client.forward_request(
                "127.0.0.1", port, "POST", "/api/x", (("Host", "backend:9999"), ("X-Test", "1")), b"body", 2.0, 2.0,
            )
        finally:
            server.close()
            await server.wait_closed()
        sent = received.decode("latin-1")
        self.assertTrue(sent.startswith("POST /api/x HTTP/1.1\r\n"))
        self.assertIn("Host: backend:9999\r\n", sent)
        self.assertIn("X-Test: 1\r\n", sent)
        self.assertTrue(sent.endswith("body"))

    async def test_no_content_length_reads_until_eof(self):
        server, port, _received = await _serve_one_response(b"HTTP/1.1 200 OK\r\n\r\nno-length-body")
        try:
            client = AsyncioHttpProxyClient()
            result = await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            self.assertEqual(result.body, b"no-length-body")
        finally:
            server.close()
            await server.wait_closed()

    async def test_connection_refused_raises_connection_error(self):
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()

        client = AsyncioHttpProxyClient()
        with self.assertRaises(HttpProxyConnectionError):
            await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 1.0, 1.0)

    async def test_malformed_status_line_raises_connection_error(self):
        server, port, _received = await _serve_one_response(b"not-a-status-line\r\n\r\n")
        try:
            client = AsyncioHttpProxyClient()
            with self.assertRaises(HttpProxyConnectionError):
                await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
        finally:
            server.close()
            await server.wait_closed()


async def _serve_persistent(handler) -> tuple[asyncio.AbstractServer, int]:
    """Serveur de test qui ne ferme jamais lui-meme la connexion -
    contrairement a _serve_one_response, necessaire pour verifier la
    reutilisation reelle d'une connexion TCP entre deux requetes."""
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


async def _close_pooled_connections(client: AsyncioHttpProxyClient) -> None:
    """Une connexion volontairement laissee dans le pool cote client
    (reutilisable, jamais fermee) laisserait sinon le handler cote
    serveur de test bloque indefiniment sur sa prochaine lecture -
    fermeture explicite necessaire avant server.close()/wait_closed()."""
    for pool in client._idle.values():
        for _reader, writer in pool:
            writer.close()
        pool.clear()


class TestAsyncioHttpProxyClientConnectionPooling(unittest.IsolatedAsyncioTestCase):
    """Retour utilisateur (audit performance) : le vrai bug corrige ici
    - une connexion TCP/TLS neuve a chaque requete relayee au lieu de
    reutiliser une connexion persistante vers le meme upstream."""

    async def test_reuses_the_same_connection_for_a_second_request_with_content_length(self):
        connections_accepted = 0

        async def handle(reader, writer):
            nonlocal connections_accepted
            connections_accepted += 1
            while True:
                data = await reader.read(4096)
                if not data:
                    return
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                await writer.drain()

        server, port = await _serve_persistent(handle)
        try:
            client = AsyncioHttpProxyClient()
            first = await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            second = await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            self.assertEqual(first.body, b"ok")
            self.assertEqual(second.body, b"ok")
            self.assertEqual(connections_accepted, 1, "la seconde requete aurait du reutiliser la connexion existante")
        finally:
            await _close_pooled_connections(client)
            server.close()
            await server.wait_closed()

    async def test_never_reuses_a_connection_without_content_length(self):
        connections_accepted = 0

        async def handle(reader, writer):
            nonlocal connections_accepted
            connections_accepted += 1
            await reader.read(4096)
            writer.write(b"HTTP/1.1 200 OK\r\n\r\nno-length-body")
            await writer.drain()
            writer.close()

        server, port = await _serve_persistent(handle)
        try:
            client = AsyncioHttpProxyClient()
            await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            self.assertEqual(connections_accepted, 2)
        finally:
            server.close()
            await server.wait_closed()

    async def test_never_reuses_a_connection_when_upstream_sends_connection_close(self):
        connections_accepted = 0

        async def handle(reader, writer):
            nonlocal connections_accepted
            connections_accepted += 1
            await reader.read(4096)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            await writer.drain()
            writer.close()

        server, port = await _serve_persistent(handle)
        try:
            client = AsyncioHttpProxyClient()
            await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            self.assertEqual(connections_accepted, 2)
        finally:
            server.close()
            await server.wait_closed()

    async def test_transparently_retries_once_when_the_pooled_connection_is_already_dead(self):
        connections_accepted = 0

        async def handle(reader, writer):
            nonlocal connections_accepted
            connections_accepted += 1
            await reader.read(4096)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            await writer.drain()
            writer.close()  # ferme cote serveur MALGRE l'absence de Connection: close

        server, port = await _serve_persistent(handle)
        try:
            client = AsyncioHttpProxyClient()
            first = await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            second = await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
            self.assertEqual(first.body, b"ok")
            self.assertEqual(second.body, b"ok")
            self.assertEqual(connections_accepted, 2, "la reprise automatique doit ouvrir une nouvelle connexion")
        finally:
            await _close_pooled_connections(client)
            server.close()
            await server.wait_closed()

    async def test_different_upstreams_never_share_a_pooled_connection(self):
        async def handle(reader, writer):
            await reader.read(4096)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            await writer.drain()
            writer.close()

        server_a, port_a = await _serve_persistent(handle)
        server_b, port_b = await _serve_persistent(handle)
        try:
            client = AsyncioHttpProxyClient()
            await client.forward_request("127.0.0.1", port_a, "GET", "/", (), b"", 2.0, 2.0)
            await client.forward_request("127.0.0.1", port_b, "GET", "/", (), b"", 2.0, 2.0)
            self.assertEqual(len(client._idle), 2)
        finally:
            await _close_pooled_connections(client)
            server_a.close()
            await server_a.wait_closed()
            server_b.close()
            await server_b.wait_closed()


class TestAsyncioHttpProxyClientWebsocket(unittest.IsolatedAsyncioTestCase):
    async def test_successful_upgrade_returns_connected_streams(self):
        holder: dict = {}

        async def handle(reader, writer):
            await reader.read(4096)
            writer.write(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
            await writer.drain()
            holder["reader"] = reader
            holder["writer"] = writer

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            client = AsyncioHttpProxyClient()
            handshake = await client.open_websocket_tunnel(
                "127.0.0.1", port, "GET", "/ws/",
                (("Host", "backend"), ("Upgrade", "websocket"), ("Connection", "Upgrade")), 2.0, 2.0,
            )
            self.assertEqual(handshake.status_code, 101)
            self.assertIsNotNone(handshake.reader)
            self.assertIsNotNone(handshake.writer)

            assert handshake.writer is not None and handshake.reader is not None
            handshake.writer.write(b"ping-from-client")
            await handshake.writer.drain()
            self.assertEqual(await holder["reader"].read(64), b"ping-from-client")

            holder["writer"].write(b"pong-from-upstream")
            await holder["writer"].drain()
            self.assertEqual(await handshake.reader.read(64), b"pong-from-upstream")
        finally:
            holder["writer"].close()
            if handshake.writer is not None:
                handshake.writer.close()
            server.close()

    async def test_upgrade_preserves_exact_byte_boundary_after_headers(self):
        holder: dict = {}
        tunnel_prefix = b"first-tunnel-bytes"

        async def handle(reader, writer):
            await reader.read(4096)
            writer.write(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n" + tunnel_prefix)
            await writer.drain()
            holder["writer"] = writer

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            client = AsyncioHttpProxyClient()
            handshake = await client.open_websocket_tunnel("127.0.0.1", port, "GET", "/ws/", (), 2.0, 2.0)
            assert handshake.reader is not None
            self.assertEqual(await handshake.reader.readexactly(len(tunnel_prefix)), tunnel_prefix)
        finally:
            holder["writer"].close()
            if handshake.writer is not None:
                handshake.writer.close()
            server.close()

    async def test_upstream_rejection_closes_connection_and_returns_no_streams(self):
        server, port, _received = await _serve_one_response(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 2\r\n\r\nno")
        try:
            client = AsyncioHttpProxyClient()
            handshake = await client.open_websocket_tunnel("127.0.0.1", port, "GET", "/ws/", (), 2.0, 2.0)
            self.assertEqual(handshake.status_code, 400)
            self.assertIsNone(handshake.reader)
            self.assertIsNone(handshake.writer)
        finally:
            server.close()

    async def test_connection_refused_raises_connection_error(self):
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()

        client = AsyncioHttpProxyClient()
        with self.assertRaises(HttpProxyConnectionError):
            await client.open_websocket_tunnel("127.0.0.1", port, "GET", "/ws/", (), 1.0, 1.0)


async def _serve_one_tls_response(raw_response: bytes, ssl_context: ssl.SSLContext) -> tuple[asyncio.AbstractServer, int]:
    async def handle(reader, writer):
        await reader.read(4096)
        writer.write(raw_response)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=ssl_context)
    port = server.sockets[0].getsockname()[1]
    return server, port


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestAsyncioHttpProxyClientTls(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        key_path = root / "server.key"
        cert_path = root / "server.pem"
        tool = OpensslCertificateTool(SubprocessRunner())
        params = SelfSignedCertParams(common_name="localhost", san_dns=("localhost",), san_ip=("127.0.0.1",))
        tool.generate_self_signed(params, key_path, cert_path)

        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        self.server_context = server_context

    async def asyncTearDown(self):
        self._tmp.cleanup()

    async def test_unverified_context_completes_handshake_against_self_signed_upstream(self):
        server, port = await _serve_one_tls_response(
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok", self.server_context,
        )
        try:
            client = AsyncioHttpProxyClient()
            result = await client.forward_request(
                "127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0,
                ssl_context=build_client_ssl_context(verify_upstream_tls=False),
            )
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.body, b"ok")
        finally:
            server.close()
            await server.wait_closed()

    async def test_verified_context_rejects_untrusted_self_signed_upstream(self):
        server, port = await _serve_one_tls_response(b"HTTP/1.1 200 OK\r\n\r\n", self.server_context)
        try:
            client = AsyncioHttpProxyClient()
            with self.assertRaises(HttpProxyConnectionError):
                await client.forward_request(
                    "127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0,
                    ssl_context=build_client_ssl_context(verify_upstream_tls=True),
                )
        finally:
            server.close()
            await server.wait_closed()

    async def test_no_ssl_context_means_plain_tcp_never_a_tls_handshake(self):
        server, port = await _serve_one_tls_response(b"HTTP/1.1 200 OK\r\n\r\n", self.server_context)
        try:
            client = AsyncioHttpProxyClient()
            with self.assertRaises(HttpProxyConnectionError):
                await client.forward_request("127.0.0.1", port, "GET", "/", (), b"", 2.0, 2.0)
        finally:
            server.close()
            await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
