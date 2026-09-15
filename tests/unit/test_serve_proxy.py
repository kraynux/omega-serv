# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest
from dataclasses import replace

from omega_serv.application.server.serve_proxy import serve_proxy
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.proxy_zone import ProxyRoundRobinState, ProxyZone, UpstreamTarget
from omega_serv.ports.http_proxy_client_port import HttpProxyConnectionError, HttpProxyResult


def _request(path="/api/users", headers=None, is_tls=False, remote_ip="203.0.113.1") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip=remote_ip, peer_ip=remote_ip, method="GET",
        path=path, raw_path=path, query="", headers=HttpHeaders.from_pairs(headers or []),
        body=None, content_length=None, is_tls=is_tls,
    )


class _FakeProxyClient:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    async def forward_request(self, host, port, method, path, headers, body, connect_timeout, read_timeout, ssl_context=None):
        self.calls.append((host, port, method, path, headers, body, connect_timeout, read_timeout, ssl_context))
        if self._error is not None:
            raise self._error
        return self._result


def _zone(**overrides):
    defaults = {"url_prefix": "/api/", "upstreams": (UpstreamTarget(host="127.0.0.1", port=3000),)}
    defaults.update(overrides)
    return ProxyZone(**defaults)


class TestServeProxy(unittest.IsolatedAsyncioTestCase):
    async def test_successful_response_translated(self):
        client = _FakeProxyClient(result=HttpProxyResult(
            status_code=200, headers=(("Content-Type", "application/json"),), body=b'{"ok":true}',
        ))
        response = await serve_proxy(_request(), _zone(), client, ProxyRoundRobinState())
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b'{"ok":true}')
        self.assertEqual(response.headers["Content-Type"], "application/json")

    async def test_query_string_forwarded(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        request = replace(_request(), query="page=2")
        await serve_proxy(request, _zone(), client, ProxyRoundRobinState())
        forwarded_path = client.calls[0][3]
        self.assertEqual(forwarded_path, "/api/users?page=2")

    async def test_upstream_connection_error_returns_bad_gateway(self):
        client = _FakeProxyClient(error=HttpProxyConnectionError("connexion refusee"))
        response = await serve_proxy(_request(), _zone(), client, ProxyRoundRobinState())
        self.assertEqual(response.status, HttpStatus.BAD_GATEWAY)

    async def test_host_header_replaced_by_default(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(_request(headers=[("Host", "public.example.com")]), _zone(), client, ProxyRoundRobinState())
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["Host"], "127.0.0.1:3000")

    async def test_host_header_preserved_when_configured(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(headers=[("Host", "public.example.com")]), _zone(preserve_host_header=True), client,
            ProxyRoundRobinState(),
        )
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["Host"], "public.example.com")

    async def test_x_forwarded_headers_set_from_real_request_never_trusted_from_client(self):
        # Retour utilisateur - injection d'en-tete classique : le client
        # ne doit JAMAIS pouvoir usurper son X-Forwarded-For en l'envoyant
        # lui-meme, la valeur reelle du serveur doit toujours l'ecraser.
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(headers=[("X-Forwarded-For", "1.2.3.4")], remote_ip="203.0.113.9"), _zone(), client,
            ProxyRoundRobinState(),
        )
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["X-Forwarded-For"], "203.0.113.9")

    async def test_x_forwarded_proto_reflects_tls_state(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(_request(is_tls=True), _zone(), client, ProxyRoundRobinState())
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["X-Forwarded-Proto"], "https")

    async def test_hop_by_hop_headers_stripped_from_outgoing_request(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(headers=[("Connection", "keep-alive"), ("Transfer-Encoding", "chunked")]), _zone(), client,
            ProxyRoundRobinState(),
        )
        headers = dict(client.calls[0][4])
        self.assertNotIn("Connection", headers)
        self.assertNotIn("Transfer-Encoding", headers)

    async def test_hop_by_hop_headers_stripped_from_response(self):
        client = _FakeProxyClient(result=HttpProxyResult(
            200, (("Connection", "close"), ("Content-Type", "text/plain")), b"hi",
        ))
        response = await serve_proxy(_request(), _zone(), client, ProxyRoundRobinState())
        self.assertNotIn("Connection", response.headers)
        self.assertEqual(response.headers["Content-Type"], "text/plain")

    async def test_forwards_to_correct_upstream(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(), _zone(upstreams=(UpstreamTarget(host="10.0.0.5", port=8443),)), client, ProxyRoundRobinState(),
        )
        host, port, method, *_ = client.calls[0]
        self.assertEqual((host, port, method), ("10.0.0.5", 8443, "GET"))

    async def test_round_robin_alternates_between_upstreams_across_requests(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(upstreams=(UpstreamTarget(host="10.0.0.1", port=3000), UpstreamTarget(host="10.0.0.2", port=3000)))
        round_robin = ProxyRoundRobinState()
        for _ in range(4):
            await serve_proxy(_request(), zone, client, round_robin)
        hosts = [call[0] for call in client.calls]
        self.assertEqual(hosts, ["10.0.0.1", "10.0.0.2", "10.0.0.1", "10.0.0.2"])

    async def test_round_robin_state_shared_across_zones_stays_independent(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone_a = _zone(url_prefix="/a/", upstreams=(UpstreamTarget(host="10.0.0.1", port=3000), UpstreamTarget(host="10.0.0.2", port=3000)))
        zone_b = _zone(url_prefix="/b/", upstreams=(UpstreamTarget(host="10.0.0.3", port=3000), UpstreamTarget(host="10.0.0.4", port=3000)))
        round_robin = ProxyRoundRobinState()
        await serve_proxy(_request(), zone_a, client, round_robin)
        await serve_proxy(_request(), zone_b, client, round_robin)
        await serve_proxy(_request(), zone_a, client, round_robin)
        hosts = [call[0] for call in client.calls]
        self.assertEqual(hosts, ["10.0.0.1", "10.0.0.3", "10.0.0.2"])

    async def test_http_upstream_never_receives_an_ssl_context(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(), _zone(), client, ProxyRoundRobinState(),
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertIsNone(client.calls[0][8])

    async def test_https_upstream_receives_verified_context_by_default(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(upstreams=(UpstreamTarget(host="10.0.0.5", port=8443, use_tls=True),))
        await serve_proxy(
            _request(), zone, client, ProxyRoundRobinState(),
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertEqual(client.calls[0][8], "verified-marker")

    async def test_https_upstream_receives_unverified_context_when_zone_disables_verification(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(
            upstreams=(UpstreamTarget(host="10.0.0.5", port=8443, use_tls=True),), verify_upstream_tls=False,
        )
        await serve_proxy(
            _request(), zone, client, ProxyRoundRobinState(),
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertEqual(client.calls[0][8], "unverified-marker")

    async def test_mixed_zone_only_https_upstream_gets_a_context(self):
        # Retour utilisateur (§12) : use_tls est une propriete PAR
        # upstream, pas par zone - un upstream HTTP dans une zone qui en
        # melange ne doit jamais recevoir de contexte TLS.
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(upstreams=(
            UpstreamTarget(host="10.0.0.1", port=3000, use_tls=False),
            UpstreamTarget(host="10.0.0.2", port=3443, use_tls=True),
        ))
        round_robin = ProxyRoundRobinState()
        await serve_proxy(
            _request(), zone, client, round_robin,
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        await serve_proxy(
            _request(), zone, client, round_robin,
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertIsNone(client.calls[0][8])
        self.assertEqual(client.calls[1][8], "verified-marker")


if __name__ == "__main__":
    unittest.main()
