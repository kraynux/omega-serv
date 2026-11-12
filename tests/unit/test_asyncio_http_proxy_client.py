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



class _ScriptedBackend:
    """Backend HTTP/1.1 persistant : rend `scripts[i]` a la i-eme requete (toutes connexions confondues),
    puis une reponse propre. Garde les connexions pour les fermer avant `server.close()`."""

    def __init__(self, scripts, close_after=()):
        self.scripts = list(scripts)
        self.close_after = set(close_after)
        self.received: list[bytes] = []
        self.connections = 0
        self.writers = []

    async def handle(self, reader, writer):
        self.connections += 1
        self.writers.append(writer)
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                length = next((int(line.split(b":")[1]) for line in head.split(b"\r\n")
                               if line.lower().startswith(b"content-length:")), 0)
                if length:
                    await reader.readexactly(length)
                self.received.append(head)
                index = len(self.received) - 1
                writer.write(self.scripts[index] if index < len(self.scripts)
                             else b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nreel")
                await writer.drain()
                if index in self.close_after:
                    break
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        writer.close()

    def methods(self) -> list[bytes]:
        return [head.split(b" ", 1)[0] for head in self.received]


class TestCorrectif262ProxyClient(unittest.IsolatedAsyncioTestCase):
    """Correctif 2.6.2 (OMEGA-SERV_PLAN_CORRECTIF_2.6.2.md §7) : D21, D22, D42. Chaque test echouait sur 2.6.1."""

    async def _run(self, backend, calls):
        server = await asyncio.start_server(backend.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = AsyncioHttpProxyClient()
        results = []
        try:
            for method, path in calls:
                try:
                    results.append(await client.forward_request(
                        "127.0.0.1", port, method, path, (), b"x=1" if method == "POST" else b"", 2.0, 2.0))
                except HttpProxyConnectionError as e:
                    results.append(e)
        finally:
            await _close_pooled_connections(client)
            for writer in backend.writers:
                writer.close()
            server.close()
            await server.wait_closed()
        return results

    async def test_d22_extra_bytes_after_body_never_reach_the_next_client(self):
        backend = _ScriptedBackend([(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"
                                     b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nPWNED!")])
        first, second, third = await self._run(backend, [("GET", "/a"), ("GET", "/b"), ("GET", "/c")])
        self.assertEqual(first.body, b"hello")
        self.assertEqual(second.body, b"reel")  # 2.6.1 : PWNED!, puis la reponse de B allait a C
        self.assertEqual(third.body, b"reel")
        self.assertEqual(len(backend.received), 3)

    async def test_d22_connection_close_token_list_and_http10_never_recycled(self):
        for response in (b"HTTP/1.1 200 OK\r\nConnection: keep-alive, Close\r\nContent-Length: 2\r\n\r\nok",
                         b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok"):
            with self.subTest(response=response):
                backend = _ScriptedBackend([response])
                await self._run(backend, [("GET", "/a"), ("GET", "/b")])
                self.assertEqual(backend.connections, 2)

    async def test_d22_bytes_arriving_while_idle_discard_the_pooled_connection(self):
        backend = _ScriptedBackend([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"])
        server = await asyncio.start_server(backend.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = AsyncioHttpProxyClient()
        try:
            await client.forward_request("127.0.0.1", port, "GET", "/a", (), b"", 2.0, 2.0)
            backend.writers[0].write(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nPWNED!")  # hors reponse
            await asyncio.sleep(0.05)
            second = await client.forward_request("127.0.0.1", port, "GET", "/b", (), b"", 2.0, 2.0)
            self.assertEqual(second.body, b"reel")
            self.assertEqual(backend.connections, 2)
        finally:
            await _close_pooled_connections(client)
            for writer in backend.writers:
                writer.close()
            server.close()
            await server.wait_closed()

    async def test_d21_ambiguous_length_is_an_error_and_never_recycled(self):
        cases = {
            "CL + TE": b"HTTP/1.1 200 OK\r\nContent-Length: 9\r\nTransfer-Encoding: chunked\r\n\r\n4\r\nabcd\r\n0\r\n\r\n",
            "CL differents": b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\nokk",
            "CL liste differente": b"HTTP/1.1 200 OK\r\nContent-Length: 2, 3\r\n\r\nokk",
            "CL signe": b"HTTP/1.1 200 OK\r\nContent-Length: +2\r\n\r\nok",
            "CL liste identique": b"HTTP/1.1 200 OK\r\nContent-Length: 2, 2\r\n\r\nok",
        }
        for label, response in cases.items():
            with self.subTest(label):
                backend = _ScriptedBackend([response])
                first, second = await self._run(backend, [("GET", "/a"), ("GET", "/b")])
                self.assertIsInstance(first, HttpProxyConnectionError)
                self.assertEqual(second.body, b"reel")
                self.assertEqual(len(backend.received), 2)  # aucune requete rejouee
                self.assertEqual(backend.connections, 2)

    async def test_d21_repeated_identical_content_length_still_accepted(self):
        # garde : deja accepte en 2.6.1, comportement inchange
        backend = _ScriptedBackend([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\nok"])
        (first,) = await self._run(backend, [("GET", "/a")])
        self.assertEqual(first.body, b"ok")

    async def test_d42_post_never_uses_a_pooled_connection_and_is_sent_once(self):
        backend = _ScriptedBackend([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nokXX\r\n"])
        _first, second = await self._run(backend, [("GET", "/a"), ("POST", "/payer")])
        self.assertEqual(second.body, b"reel")
        self.assertEqual(backend.methods().count(b"POST"), 1)  # 2.6.1 : 2

    async def test_d42_non_replayable_methods_open_a_new_connection(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method):
                backend = _ScriptedBackend([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"])
                await self._run(backend, [("GET", "/a"), (method, "/b")])
                self.assertEqual(backend.connections, 2)

    async def test_d42_get_is_not_replayed_once_the_response_has_started(self):
        backend = _ScriptedBackend([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok",
                                    b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nabc"], close_after={1})
        _first, second = await self._run(backend, [("GET", "/a"), ("GET", "/b")])
        self.assertIsInstance(second, HttpProxyConnectionError)
        self.assertEqual(len(backend.received), 2)  # coupee en pleine reponse : jamais rejouee


if __name__ == "__main__":
    unittest.main()
