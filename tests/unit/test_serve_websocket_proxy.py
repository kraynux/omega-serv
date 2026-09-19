"""Le choix d'upstream/la construction des en-tetes/le mode d'echec
utilisent un double `HttpProxyClientPort` (meme patron que
test_serve_proxy.py) - mais le relai bidirectionnel lui-meme (le coeur
de ce module) est teste avec de VRAIS sockets TCP loopback des deux
cotes (jamais un double pour ca), seule maniere honnete de verifier
que des octets ecrits d'un cote arrivent reellement de l'autre.

Piege deja documente dans ce projet (Phase 9, service manager) : depuis
Python 3.12.1, `asyncio.Server.wait_closed()` attend, SANS aucune
limite, que toutes les connexions actives se terminent - jamais appele
ici sans avoir d'abord ferme explicitement chaque writer ouvert par le
test, exactement la meme lecon que `AsyncioHttpServer.shutdown()`."""
import asyncio
import contextlib
import unittest
from dataclasses import replace

from omega_serv.application.server.serve_websocket_proxy import serve_websocket_proxy
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.routing.proxy_zone import ProxyRoundRobinState, ProxyZone, UpstreamTarget
from omega_serv.ports.http_proxy_client_port import (
    HttpProxyConnectionError,
    WebSocketUpstreamHandshake,
)


def _request(path="/ws/chat", headers=None) -> HttpRequest:
    default_headers = [("Connection", "Upgrade"), ("Upgrade", "websocket")]
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method="GET",
        path=path, raw_path=path, query="", headers=HttpHeaders.from_pairs(headers or default_headers),
        body=None, content_length=None, is_tls=False,
    )


def _zone(**overrides):
    defaults = {"url_prefix": "/ws/", "upstreams": (UpstreamTarget(host="127.0.0.1", port=9000),), "websocket_enabled": True}
    defaults.update(overrides)
    return ProxyZone(**defaults)


class _FakeProxyClient:
    def __init__(self, handshake=None, error=None):
        self._handshake = handshake
        self._error = error
        self.calls = []

    async def open_websocket_tunnel(self, host, port, method, path, headers, connect_timeout, read_timeout, ssl_context=None):
        self.calls.append((host, port, method, path, headers, connect_timeout, read_timeout, ssl_context))
        if self._error is not None:
            raise self._error
        return self._handshake


class _ConnectedPair:
    """Une vraie paire client<->serveur TCP loopback. `connector_*` est
    le cote qui a appele `open_connection` (simule qui que ce soit qui
    INITIE la connexion) ; `accepted_*` est le cote accepte par
    `start_server` (simule qui que ce soit qui la RECOIT)."""

    def __init__(self, server, connector_reader, connector_writer, accepted_reader, accepted_writer):
        self.server = server
        self.connector_reader = connector_reader
        self.connector_writer = connector_writer
        self.accepted_reader = accepted_reader
        self.accepted_writer = accepted_writer

    @classmethod
    async def open(cls) -> "_ConnectedPair":
        accepted = asyncio.Event()
        holder: dict = {}

        async def handle(reader, writer):
            holder["reader"] = reader
            holder["writer"] = writer
            accepted.set()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        connector_reader, connector_writer = await asyncio.open_connection("127.0.0.1", port)
        await accepted.wait()
        return cls(server, connector_reader, connector_writer, holder["reader"], holder["writer"])

    async def close(self) -> None:
        for writer in (self.connector_writer, self.accepted_writer):
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        self.server.close()


class TestServeWebsocketProxy(unittest.IsolatedAsyncioTestCase):
    async def test_relays_bytes_bidirectionally_after_successful_upgrade(self):
        client_pair = await _ConnectedPair.open()
        upstream_pair = await _ConnectedPair.open()

        try:
            handshake = WebSocketUpstreamHandshake(
                status_code=101, headers=(("Upgrade", "websocket"), ("Connection", "Upgrade")),
                reader=upstream_pair.connector_reader, writer=upstream_pair.connector_writer,
            )
            proxy_client = _FakeProxyClient(handshake=handshake)

            task = asyncio.create_task(serve_websocket_proxy(
                _request(), _zone(), proxy_client, ProxyRoundRobinState(),
                client_pair.accepted_reader, client_pair.accepted_writer,
            ))

            status_line = await client_pair.connector_reader.readline()
            self.assertIn(b"101", status_line)
            while (await client_pair.connector_reader.readline()) not in (b"\r\n", b""):
                pass

            client_pair.connector_writer.write(b"hello-from-browser")
            await client_pair.connector_writer.drain()
            self.assertEqual(await upstream_pair.accepted_reader.read(64), b"hello-from-browser")

            upstream_pair.accepted_writer.write(b"hello-from-backend")
            await upstream_pair.accepted_writer.drain()
            self.assertEqual(await client_pair.connector_reader.read(64), b"hello-from-backend")

            upstream_pair.accepted_writer.close()
            status = await asyncio.wait_for(task, timeout=3)
            self.assertEqual(status, 101)
        finally:
            await client_pair.close()
            await upstream_pair.close()

    async def test_upstream_connection_error_writes_bad_gateway_to_client(self):
        client_pair = await _ConnectedPair.open()
        try:
            proxy_client = _FakeProxyClient(error=HttpProxyConnectionError("connexion refusee"))
            status = await serve_websocket_proxy(
                _request(), _zone(), proxy_client, ProxyRoundRobinState(),
                client_pair.accepted_reader, client_pair.accepted_writer,
            )
            self.assertEqual(status, 502)
            status_line = await client_pair.connector_reader.readline()
            self.assertIn(b"502", status_line)
        finally:
            await client_pair.close()

    async def test_upstream_rejection_relays_status_without_starting_tunnel(self):
        client_pair = await _ConnectedPair.open()
        try:
            handshake = WebSocketUpstreamHandshake(status_code=400, headers=(("Content-Type", "text/plain"),), reader=None, writer=None)
            proxy_client = _FakeProxyClient(handshake=handshake)
            status = await asyncio.wait_for(serve_websocket_proxy(
                _request(), _zone(), proxy_client, ProxyRoundRobinState(),
                client_pair.accepted_reader, client_pair.accepted_writer,
            ), timeout=3)
            self.assertEqual(status, 400)
            status_line = await client_pair.connector_reader.readline()
            self.assertIn(b"400", status_line)
        finally:
            await client_pair.close()

    async def test_forwards_to_chosen_upstream_with_query_string(self):
        client_pair = await _ConnectedPair.open()
        try:
            proxy_client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
            request = replace(_request(path="/ws/chat"), query="room=1")
            await serve_websocket_proxy(
                request, _zone(), proxy_client, ProxyRoundRobinState(),
                client_pair.accepted_reader, client_pair.accepted_writer,
            )
            host, port, method, path, *_ = proxy_client.calls[0]
            self.assertEqual((host, port, method, path), ("127.0.0.1", 9000, "GET", "/ws/chat?room=1"))
        finally:
            await client_pair.close()

    async def test_connection_and_upgrade_headers_preserved_outgoing(self):
        client_pair = await _ConnectedPair.open()
        try:
            proxy_client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
            await serve_websocket_proxy(
                _request(), _zone(), proxy_client, ProxyRoundRobinState(),
                client_pair.accepted_reader, client_pair.accepted_writer,
            )
            headers = dict(proxy_client.calls[0][4])
            self.assertEqual(headers["connection"], "Upgrade")
            self.assertEqual(headers["upgrade"], "websocket")
        finally:
            await client_pair.close()

    async def test_https_upstream_receives_verified_context_by_default(self):
        client_pair = await _ConnectedPair.open()
        try:
            proxy_client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
            zone = _zone(upstreams=(UpstreamTarget(host="10.0.0.5", port=8443, use_tls=True),))
            await serve_websocket_proxy(
                _request(), zone, proxy_client, ProxyRoundRobinState(),
                client_pair.accepted_reader, client_pair.accepted_writer,
                client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
            )
            self.assertEqual(proxy_client.calls[0][7], "verified-marker")
        finally:
            await client_pair.close()

    async def test_http_upstream_never_receives_an_ssl_context(self):
        client_pair = await _ConnectedPair.open()
        try:
            proxy_client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
            await serve_websocket_proxy(
                _request(), _zone(), proxy_client, ProxyRoundRobinState(),
                client_pair.accepted_reader, client_pair.accepted_writer,
                client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
            )
            self.assertIsNone(proxy_client.calls[0][7])
        finally:
            await client_pair.close()


if __name__ == "__main__":
    unittest.main()
