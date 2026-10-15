import asyncio
import unittest
from dataclasses import replace

from omega_serv.application.server.proxy_cache_locks import ProxyCacheLocks
from omega_serv.application.server.serve_proxy import (
    AllUpstreamsAtCapacityError,
    resolve_upstream,
    serve_proxy,
)
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    ProxyLoadBalancerState,
    ProxyZone,
    RoutingRule,
    UpstreamTarget,
    sticky_cookie_value_for,
    upstream_key,
)
from omega_serv.ports.http_proxy_client_port import HttpProxyConnectionError, HttpProxyResult


class _InMemoryProxyCacheStore:
    """Double simple pour tester l'orchestration cache de `serve_proxy()`
    sans dependre du vrai stockage disque (deja teste en isolation dans
    `test_filesystem_proxy_cache_store.py`)."""

    def __init__(self):
        self._entries = {}

    def get(self, zone_key, cache_key):
        return self._entries.get((zone_key, cache_key))

    def get_variants(self, zone_key, primary_key):
        return tuple(
            entry for (zk, ck), entry in self._entries.items()
            if zk == zone_key and ck.startswith(f"{primary_key}--")
        )

    def set(self, zone_key, cache_key, entry):
        self._entries[(zone_key, cache_key)] = entry

    def delete(self, zone_key, cache_key):
        self._entries.pop((zone_key, cache_key), None)

    def clear(self, *, zone_key=None):
        if zone_key is None:
            count = len(self._entries)
            self._entries.clear()
            return count
        keys = [k for k in self._entries if k[0] == zone_key]
        for k in keys:
            del self._entries[k]
        return len(keys)

    def stats(self, *, zone_key=None):
        raise NotImplementedError


def _request(path="/api/users", headers=None, is_tls=False, remote_ip="203.0.113.1", method="GET") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip=remote_ip, peer_ip=remote_ip, method=method,
        path=path, raw_path=path, query="", headers=HttpHeaders.from_pairs(headers or []),
        body=None, content_length=None, is_tls=is_tls,
    )


class _FakeProxyClient:
    """`errors` : liste optionnelle d'exceptions a lever dans l'ORDRE
    des appels (une par appel) - permet de simuler "le premier upstream
    echoue, le second repond" pour les tests de retry (§18.4). Si plus
    courte que le nombre d'appels, `result`/`error` s'applique au-dela."""

    def __init__(self, result=None, error=None, errors=None, delay=0.0):
        self._result = result
        self._error = error
        self._errors = list(errors) if errors is not None else None
        self._delay = delay
        self.calls = []

    async def forward_request(self, host, port, method, path, headers, body, connect_timeout, read_timeout, ssl_context=None):
        if self._delay:
            await asyncio.sleep(self._delay)
        call_index = len(self.calls)
        self.calls.append((host, port, method, path, headers, body, connect_timeout, read_timeout, ssl_context))
        if self._errors is not None and call_index < len(self._errors):
            error = self._errors[call_index]
            if error is not None:
                raise error
            return self._result
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
        response = await serve_proxy(_request(), _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b'{"ok":true}')
        self.assertEqual(response.headers["Content-Type"], "application/json")

    async def test_query_string_forwarded(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        request = replace(_request(), query="page=2")
        await serve_proxy(request, _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        forwarded_path = client.calls[0][3]
        self.assertEqual(forwarded_path, "/api/users?page=2")

    async def test_upstream_connection_error_returns_bad_gateway(self):
        client = _FakeProxyClient(error=HttpProxyConnectionError("connexion refusee"))
        response = await serve_proxy(_request(), _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, HttpStatus.BAD_GATEWAY)

    async def test_host_header_replaced_by_default(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(headers=[("Host", "public.example.com")]), _zone(), client, ProxyLoadBalancerState(),
            ProxyHealthState(),
        )
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["Host"], "127.0.0.1:3000")

    async def test_host_header_preserved_when_configured(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(headers=[("Host", "public.example.com")]), _zone(preserve_host_header=True), client,
            ProxyLoadBalancerState(), ProxyHealthState(),
        )
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["Host"], "public.example.com")

    async def test_x_forwarded_headers_set_from_real_request_never_trusted_from_client(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(headers=[("X-Forwarded-For", "1.2.3.4")], remote_ip="203.0.113.9"), _zone(), client,
            ProxyLoadBalancerState(), ProxyHealthState(),
        )
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["X-Forwarded-For"], "203.0.113.9")

    async def test_x_forwarded_proto_reflects_tls_state(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(_request(is_tls=True), _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["X-Forwarded-Proto"], "https")

    async def test_hop_by_hop_headers_stripped_from_outgoing_request(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(headers=[("Connection", "keep-alive"), ("Transfer-Encoding", "chunked")]), _zone(), client,
            ProxyLoadBalancerState(), ProxyHealthState(),
        )
        headers = dict(client.calls[0][4])
        self.assertNotIn("Connection", headers)
        self.assertNotIn("Transfer-Encoding", headers)

    async def test_hop_by_hop_headers_stripped_from_response(self):
        client = _FakeProxyClient(result=HttpProxyResult(
            200, (("Connection", "close"), ("Content-Type", "text/plain")), b"hi",
        ))
        response = await serve_proxy(_request(), _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertNotIn("Connection", response.headers)
        self.assertEqual(response.headers["Content-Type"], "text/plain")

    async def test_forwards_to_correct_upstream(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(), _zone(upstreams=(UpstreamTarget(host="10.0.0.5", port=8443),)), client,
            ProxyLoadBalancerState(), ProxyHealthState(),
        )
        host, port, method, *_ = client.calls[0]
        self.assertEqual((host, port, method), ("10.0.0.5", 8443, "GET"))

    async def test_round_robin_alternates_between_upstreams_across_requests(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(upstreams=(UpstreamTarget(host="10.0.0.1", port=3000), UpstreamTarget(host="10.0.0.2", port=3000)))
        round_robin = ProxyLoadBalancerState()
        health_state = ProxyHealthState()
        for _ in range(4):
            await serve_proxy(_request(), zone, client, round_robin, health_state)
        hosts = [call[0] for call in client.calls]
        self.assertEqual(hosts, ["10.0.0.1", "10.0.0.2", "10.0.0.1", "10.0.0.2"])

    async def test_round_robin_state_shared_across_zones_stays_independent(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone_a = _zone(url_prefix="/a/", upstreams=(UpstreamTarget(host="10.0.0.1", port=3000), UpstreamTarget(host="10.0.0.2", port=3000)))
        zone_b = _zone(url_prefix="/b/", upstreams=(UpstreamTarget(host="10.0.0.3", port=3000), UpstreamTarget(host="10.0.0.4", port=3000)))
        round_robin = ProxyLoadBalancerState()
        health_state = ProxyHealthState()
        await serve_proxy(_request(), zone_a, client, round_robin, health_state)
        await serve_proxy(_request(), zone_b, client, round_robin, health_state)
        await serve_proxy(_request(), zone_a, client, round_robin, health_state)
        hosts = [call[0] for call in client.calls]
        self.assertEqual(hosts, ["10.0.0.1", "10.0.0.3", "10.0.0.2"])

    async def test_http_upstream_never_receives_an_ssl_context(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(
            _request(), _zone(), client, ProxyLoadBalancerState(), ProxyHealthState(),
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertIsNone(client.calls[0][8])

    async def test_https_upstream_receives_verified_context_by_default(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(upstreams=(UpstreamTarget(host="10.0.0.5", port=8443, use_tls=True),))
        await serve_proxy(
            _request(), zone, client, ProxyLoadBalancerState(), ProxyHealthState(),
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertEqual(client.calls[0][8], "verified-marker")

    async def test_https_upstream_receives_unverified_context_when_zone_disables_verification(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(
            upstreams=(UpstreamTarget(host="10.0.0.5", port=8443, use_tls=True),), verify_upstream_tls=False,
        )
        await serve_proxy(
            _request(), zone, client, ProxyLoadBalancerState(), ProxyHealthState(),
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertEqual(client.calls[0][8], "unverified-marker")

    async def test_mixed_zone_only_https_upstream_gets_a_context(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = _zone(upstreams=(
            UpstreamTarget(host="10.0.0.1", port=3000, use_tls=False),
            UpstreamTarget(host="10.0.0.2", port=3443, use_tls=True),
        ))
        round_robin = ProxyLoadBalancerState()
        health_state = ProxyHealthState()
        await serve_proxy(
            _request(), zone, client, round_robin, health_state,
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        await serve_proxy(
            _request(), zone, client, round_robin, health_state,
            client_ssl_context_verified="verified-marker", client_ssl_context_unverified="unverified-marker",
        )
        self.assertIsNone(client.calls[0][8])
        self.assertEqual(client.calls[1][8], "verified-marker")


class TestServeProxyStickySession(unittest.IsolatedAsyncioTestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def _zone(self, **overrides):
        defaults = {
            "url_prefix": "/api/", "upstreams": (self._UPSTREAM_A, self._UPSTREAM_B),
            "sticky_session_enabled": True,
        }
        defaults.update(overrides)
        return ProxyZone(**defaults)

    async def test_first_response_sets_sticky_cookie_for_the_chosen_upstream(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone()
        response = await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertIn("Set-Cookie", response.headers)
        self.assertIn("omega_proxy_sticky=", response.headers["Set-Cookie"])

    async def test_request_with_valid_sticky_cookie_always_reaches_same_upstream(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone()
        cookie_value = sticky_cookie_value_for(self._UPSTREAM_B)
        load_balancer = ProxyLoadBalancerState()
        health_state = ProxyHealthState()
        for _ in range(4):
            await serve_proxy(
                _request(headers=[("Cookie", f"omega_proxy_sticky={cookie_value}")]), zone, client, load_balancer,
                health_state,
            )
        hosts = [call[0] for call in client.calls]
        self.assertEqual(hosts, ["10.0.0.2"] * 4)

    async def test_forged_sticky_cookie_falls_back_to_normal_strategy(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone()
        await serve_proxy(
            _request(headers=[("Cookie", "omega_proxy_sticky=not-a-real-value")]), zone, client,
            ProxyLoadBalancerState(), ProxyHealthState(),
        )
        self.assertEqual(client.calls[0][0], "10.0.0.1")

    async def test_sticky_cookie_not_set_when_disabled(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone(sticky_session_enabled=False)
        response = await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertNotIn("Set-Cookie", response.headers)

    async def test_sticky_cookie_not_set_on_upstream_connection_error(self):
        client = _FakeProxyClient(error=HttpProxyConnectionError("connexion refusee"))
        zone = self._zone()
        response = await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertNotIn("Set-Cookie", response.headers)

    async def test_sticky_cookie_follows_upstream_that_actually_served_after_retry(self):
        """§18.4 x §17 : si le premier choix (sticky vers A) echoue et
        que le retry reussit sur B, le cookie doit desormais pointer
        vers B - jamais rester colle a l'upstream qui vient d'echouer."""
        client = _FakeProxyClient(errors=[HttpProxyConnectionError("boom"), None], result=HttpProxyResult(200, (), b""))
        zone = self._zone()
        cookie_for_a = sticky_cookie_value_for(self._UPSTREAM_A)
        response = await serve_proxy(
            _request(headers=[("Cookie", f"omega_proxy_sticky={cookie_for_a}")]), zone, client,
            ProxyLoadBalancerState(), ProxyHealthState(),
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0][0], "10.0.0.1")
        self.assertEqual(client.calls[1][0], "10.0.0.2")
        self.assertIn(sticky_cookie_value_for(self._UPSTREAM_B), response.headers["Set-Cookie"])


class TestServeProxyRoutingRules(unittest.IsolatedAsyncioTestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def _zone(self, *rules, **overrides):
        defaults = {"url_prefix": "/api/", "upstreams": (self._UPSTREAM_A, self._UPSTREAM_B), "routing_rules": rules}
        defaults.update(overrides)
        return ProxyZone(**defaults)

    async def test_matching_header_rule_forces_target_upstream(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        rule = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule)
        await serve_proxy(
            _request(headers=[("X-Canary", "true")]), zone, client, ProxyLoadBalancerState(), ProxyHealthState(),
        )
        self.assertEqual(client.calls[0][0], "10.0.0.2")

    async def test_non_matching_header_falls_back_to_normal_strategy(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        rule = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule)
        await serve_proxy(
            _request(headers=[("X-Canary", "false")]), zone, client, ProxyLoadBalancerState(), ProxyHealthState(),
        )
        self.assertEqual(client.calls[0][0], "10.0.0.1")

    async def test_header_rule_takes_precedence_over_sticky_cookie(self):
        """§27.2 : la regle d'en-tete l'emporte toujours sur le cookie
        sticky, meme si un cookie valide pointe vers un AUTRE upstream."""
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        rule = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule, sticky_session_enabled=True)
        cookie_for_a = sticky_cookie_value_for(self._UPSTREAM_A)
        await serve_proxy(
            _request(headers=[("X-Canary", "true"), ("Cookie", f"omega_proxy_sticky={cookie_for_a}")]),
            zone, client, ProxyLoadBalancerState(), ProxyHealthState(),
        )
        self.assertEqual(client.calls[0][0], "10.0.0.2")

    async def test_rule_targeting_an_ineligible_upstream_falls_back_to_strategy(self):
        """§27.2 etape 3 x §18.3 : un upstream DOWN ne doit jamais etre
        force par une regle - retombe sur la strategie active."""
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        rule = RoutingRule(header_name="x-canary", pattern="true", upstream_key=upstream_key(self._UPSTREAM_B))
        zone = self._zone(rule)
        health_state = ProxyHealthState()
        for _ in range(zone.unhealthy_after):
            health_state.record_failure(zone.url_prefix, self._UPSTREAM_B, unhealthy_after=zone.unhealthy_after)
        await serve_proxy(
            _request(headers=[("X-Canary", "true")]), zone, client, ProxyLoadBalancerState(), health_state,
        )
        self.assertEqual(client.calls[0][0], "10.0.0.1")


class TestServeProxyHealthAndRetry(unittest.IsolatedAsyncioTestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)

    def _zone(self, **overrides):
        defaults = {"url_prefix": "/api/", "upstreams": (self._UPSTREAM_A, self._UPSTREAM_B)}
        defaults.update(overrides)
        return ProxyZone(**defaults)

    async def test_connection_failure_marks_upstream_down_after_threshold(self):
        client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
        zone = self._zone(upstreams=(self._UPSTREAM_A,), unhealthy_after=2)
        health_state = ProxyHealthState()
        await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), health_state)
        self.assertEqual(health_state.status_for(zone.url_prefix, self._UPSTREAM_A), "up")
        await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), health_state)
        self.assertEqual(health_state.status_for(zone.url_prefix, self._UPSTREAM_A), "down")

    async def test_successful_response_keeps_upstream_up(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone(upstreams=(self._UPSTREAM_A,))
        health_state = ProxyHealthState()
        await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), health_state)
        self.assertEqual(health_state.status_for(zone.url_prefix, self._UPSTREAM_A), "up")

    async def test_down_upstream_is_excluded_from_normal_selection(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone()
        health_state = ProxyHealthState()
        for _ in range(zone.unhealthy_after):
            health_state.record_failure(zone.url_prefix, self._UPSTREAM_A, unhealthy_after=zone.unhealthy_after)
        for _ in range(4):
            await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), health_state)
        hosts = {call[0] for call in client.calls}
        self.assertEqual(hosts, {"10.0.0.2"})

    async def test_all_upstreams_down_falls_back_to_trying_anyway(self):
        """Angle mort §18.1 : plutot que de refuser sec, retenter quand
        meme le "moins pire" si TOUS les upstreams sont DOWN."""
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone(upstreams=(self._UPSTREAM_A,))
        health_state = ProxyHealthState()
        for _ in range(zone.unhealthy_after):
            health_state.record_failure(zone.url_prefix, self._UPSTREAM_A, unhealthy_after=zone.unhealthy_after)
        response = await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), health_state)
        self.assertEqual(response.status, 200)
        self.assertEqual(client.calls[0][0], "10.0.0.1")

    async def test_get_retries_once_on_a_different_upstream_after_connection_error(self):
        client = _FakeProxyClient(errors=[HttpProxyConnectionError("boom"), None], result=HttpProxyResult(200, (), b""))
        zone = self._zone(load_balancing="round_robin")
        response = await serve_proxy(_request(method="GET"), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, 200)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual({client.calls[0][0], client.calls[1][0]}, {"10.0.0.1", "10.0.0.2"})
        self.assertNotEqual(client.calls[0][0], client.calls[1][0])

    async def test_post_never_retries_on_connection_error(self):
        client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
        zone = self._zone()
        response = await serve_proxy(_request(method="POST"), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, HttpStatus.BAD_GATEWAY)
        self.assertEqual(len(client.calls), 1)

    async def test_single_upstream_zone_never_retries(self):
        client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
        zone = self._zone(upstreams=(self._UPSTREAM_A,))
        response = await serve_proxy(_request(method="GET"), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, HttpStatus.BAD_GATEWAY)
        self.assertEqual(len(client.calls), 1)

    async def test_retry_also_fails_still_returns_bad_gateway(self):
        client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
        zone = self._zone()
        response = await serve_proxy(_request(method="GET"), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, HttpStatus.BAD_GATEWAY)
        self.assertEqual(len(client.calls), 2)


class TestBackpressure(unittest.IsolatedAsyncioTestCase):
    _UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000, max_concurrent_requests=1)
    _UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000, max_concurrent_requests=1)

    def _zone(self, **overrides):
        defaults = {"url_prefix": "/api/", "upstreams": (self._UPSTREAM_A,)}
        defaults.update(overrides)
        return ProxyZone(**defaults)

    def test_resolve_upstream_raises_when_sole_healthy_upstream_is_saturated(self):
        zone = self._zone()
        load_balancer = ProxyLoadBalancerState()
        load_balancer.acquire(zone.url_prefix, self._UPSTREAM_A)
        with self.assertRaises(AllUpstreamsAtCapacityError):
            resolve_upstream(_request(), zone, load_balancer, ProxyHealthState())

    def test_resolve_upstream_picks_the_upstream_with_free_capacity(self):
        zone = self._zone(upstreams=(self._UPSTREAM_A, self._UPSTREAM_B))
        load_balancer = ProxyLoadBalancerState()
        load_balancer.acquire(zone.url_prefix, self._UPSTREAM_A)
        picked = resolve_upstream(_request(), zone, load_balancer, ProxyHealthState())
        self.assertEqual(picked, self._UPSTREAM_B)

    async def test_serve_proxy_returns_503_when_all_upstreams_saturated(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone()
        load_balancer = ProxyLoadBalancerState()
        load_balancer.acquire(zone.url_prefix, self._UPSTREAM_A)
        response = await serve_proxy(_request(), zone, client, load_balancer, ProxyHealthState())
        self.assertEqual(response.status, HttpStatus.SERVICE_UNAVAILABLE)
        self.assertEqual(len(client.calls), 0)

    async def test_serve_proxy_succeeds_once_capacity_frees_up(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone()
        load_balancer = ProxyLoadBalancerState()
        load_balancer.acquire(zone.url_prefix, self._UPSTREAM_A)
        load_balancer.release(zone.url_prefix, self._UPSTREAM_A)
        response = await serve_proxy(_request(), zone, client, load_balancer, ProxyHealthState())
        self.assertEqual(response.status, 200)

    async def test_unlimited_upstream_never_raises(self):
        unlimited = UpstreamTarget(host="10.0.0.3", port=3000)
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone(upstreams=(unlimited,))
        response = await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, 200)

    async def test_down_upstream_is_not_confused_with_saturation(self):
        """§18.1 vs §20 : un upstream DOWN (jamais sature) retombe sur
        le repli "retenter quand meme", jamais un 503 de backpressure."""
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        zone = self._zone(unhealthy_after=1)
        health_state = ProxyHealthState()
        health_state.record_failure(zone.url_prefix, self._UPSTREAM_A, unhealthy_after=1)
        response = await serve_proxy(_request(), zone, client, ProxyLoadBalancerState(), health_state)
        self.assertEqual(response.status, 200)


class TestServeProxyCache(unittest.IsolatedAsyncioTestCase):
    def _zone(self, **overrides):
        defaults = {
            "url_prefix": "/api/", "upstreams": (UpstreamTarget(host="127.0.0.1", port=3000),),
            "cache_enabled": True,
        }
        defaults.update(overrides)
        return ProxyZone(**defaults)

    async def _serve(self, zone, client, request=None, store=None, locks=None, metrics=None):
        return await serve_proxy(
            request or _request(), zone, client, ProxyLoadBalancerState(), ProxyHealthState(),
            cache_store=store or _InMemoryProxyCacheStore(), cache_locks=locks or ProxyCacheLocks(),
            cache_metrics=metrics,
        )

    async def test_cache_disabled_is_bypass_and_never_stores(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b"body"))
        zone = self._zone(cache_enabled=False)
        store = _InMemoryProxyCacheStore()
        response = await self._serve(zone, client, store=store)
        self.assertEqual(response.headers["X-Omega-Cache"], "BYPASS")
        self.assertEqual(len(client.calls), 1)

    async def test_first_request_is_a_miss_second_is_a_hit(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Content-Type", "text/plain"),), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        first = await self._serve(zone, client, store=store)
        self.assertEqual(first.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(first.body, b"body")
        second = await self._serve(zone, client, store=store)
        self.assertEqual(second.headers["X-Omega-Cache"], "HIT")
        self.assertEqual(second.body, b"body")
        self.assertEqual(len(client.calls), 1)  # le backend n'est touche qu'une seule fois

    async def test_post_is_never_cached_even_when_zone_allows_caching(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        await self._serve(zone, client, request=_request(method="POST"), store=store)
        await self._serve(zone, client, request=_request(method="POST"), store=store)
        self.assertEqual(len(client.calls), 2)

    async def test_error_response_is_never_cached(self):
        client = _FakeProxyClient(result=HttpProxyResult(500, (), b"oops"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        first = await self._serve(zone, client, store=store)
        second = await self._serve(zone, client, store=store)
        self.assertEqual(first.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(second.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(len(client.calls), 2)

    async def test_set_cookie_response_is_never_cached_by_default(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Set-Cookie", "session=abc"),), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        await self._serve(zone, client, store=store)
        second = await self._serve(zone, client, store=store)
        self.assertEqual(second.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(len(client.calls), 2)

    async def test_set_cookie_response_is_cached_when_zone_assumes_it(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Set-Cookie", "session=abc"),), b"body"))
        zone = self._zone(cache_allow_set_cookie=True)
        store = _InMemoryProxyCacheStore()
        await self._serve(zone, client, store=store)
        second = await self._serve(zone, client, store=store)
        self.assertEqual(second.headers["X-Omega-Cache"], "HIT")
        self.assertEqual(len(client.calls), 1)

    async def test_upstream_no_store_blocks_caching(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Cache-Control", "no-store"),), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        await self._serve(zone, client, store=store)
        second = await self._serve(zone, client, store=store)
        self.assertEqual(second.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(len(client.calls), 2)

    async def test_ignoring_upstream_headers_caches_even_a_no_store_response(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Cache-Control", "no-store"),), b"body"))
        zone = self._zone(cache_respect_upstream_headers=False)
        store = _InMemoryProxyCacheStore()
        await self._serve(zone, client, store=store)
        second = await self._serve(zone, client, store=store)
        self.assertEqual(second.headers["X-Omega-Cache"], "HIT")

    async def test_vary_mismatch_is_a_miss_not_a_wrong_hit(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Vary", "Accept-Encoding"),), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        await self._serve(zone, client, request=_request(headers=[("Accept-Encoding", "gzip")]), store=store)
        second = await self._serve(
            zone, client, request=_request(headers=[("Accept-Encoding", "br")]), store=store,
        )
        self.assertEqual(second.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(len(client.calls), 2)

    async def test_vary_match_is_a_hit(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Vary", "Accept-Encoding"),), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        await self._serve(zone, client, request=_request(headers=[("Accept-Encoding", "gzip")]), store=store)
        second = await self._serve(
            zone, client, request=_request(headers=[("Accept-Encoding", "gzip")]), store=store,
        )
        self.assertEqual(second.headers["X-Omega-Cache"], "HIT")
        self.assertEqual(len(client.calls), 1)

    async def test_two_vary_variants_coexist_both_cached(self):
        """Phase 8bis (§23 angle mort #3 reouvert) : deux variantes d'une
        meme ressource (ici Accept-Encoding gzip vs br) coexistent
        REELLEMENT en cache, jamais "la derniere ecrase la premiere" -
        une fois les deux posees, les DEUX servent un HIT, le backend
        n'est touche que deux fois au total (une par variante)."""
        client = _FakeProxyClient(result=HttpProxyResult(200, (("Vary", "Accept-Encoding"),), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        gzip_request = _request(headers=[("Accept-Encoding", "gzip")])
        br_request = _request(headers=[("Accept-Encoding", "br")])

        first_gzip = await self._serve(zone, client, request=gzip_request, store=store)
        first_br = await self._serve(zone, client, request=br_request, store=store)
        self.assertEqual(first_gzip.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(first_br.headers["X-Omega-Cache"], "MISS")
        self.assertEqual(len(client.calls), 2)

        second_gzip = await self._serve(zone, client, request=gzip_request, store=store)
        second_br = await self._serve(zone, client, request=br_request, store=store)
        self.assertEqual(second_gzip.headers["X-Omega-Cache"], "HIT")
        self.assertEqual(second_br.headers["X-Omega-Cache"], "HIT")
        self.assertEqual(len(client.calls), 2)  # toujours deux au total - aucune des deux variantes n'a ete ecrasee

    async def test_cache_metrics_record_hits_and_misses_when_provided(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b"body"))
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        metrics = ProxyCacheMetrics()
        await self._serve(zone, client, store=store, metrics=metrics)
        await self._serve(zone, client, store=store, metrics=metrics)
        self.assertEqual(metrics.snapshot(zone.url_prefix), (1, 1))

    async def test_bypass_never_touches_cache_metrics(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b"body"))
        zone = self._zone(cache_enabled=False)
        metrics = ProxyCacheMetrics()
        await self._serve(zone, client, metrics=metrics)
        self.assertEqual(metrics.snapshot(), (0, 0))

    async def test_concurrent_misses_on_the_same_key_only_hit_the_backend_once(self):
        """Protection anti-stampede (§21) : plusieurs requetes CONCURRENTES
        sur une cle vide ne doivent declencher qu'UN SEUL appel reel au
        backend, les autres attendent son resultat."""
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b"body"), delay=0.05)
        zone = self._zone()
        store = _InMemoryProxyCacheStore()
        locks = ProxyCacheLocks()
        results = await asyncio.gather(*(
            self._serve(zone, client, store=store, locks=locks) for _ in range(5)
        ))
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(all(r.body == b"body" for r in results))


class TestProxyHopGuard(unittest.IsolatedAsyncioTestCase):
    """Garde-fou anti-boucle indirecte entre instances (§23 angle mort
    #16, §29.9) - MAX_PROXY_HOPS importe directement plutot que
    duplique, jamais suppose."""

    async def test_first_hop_sets_header_to_one(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        await serve_proxy(_request(), _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["X-Omega-Proxy-Hops"], "1")

    async def test_existing_header_is_incremented_not_duplicated(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        request = _request(headers=[("X-Omega-Proxy-Hops", "3")])
        await serve_proxy(request, _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        outgoing = client.calls[0][4]
        hop_headers = [v for n, v in outgoing if n == "X-Omega-Proxy-Hops"]
        self.assertEqual(hop_headers, ["4"])

    async def test_malformed_header_treated_as_zero(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        request = _request(headers=[("X-Omega-Proxy-Hops", "pas-un-nombre")])
        await serve_proxy(request, _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        headers = dict(client.calls[0][4])
        self.assertEqual(headers["X-Omega-Proxy-Hops"], "1")

    async def test_refuses_at_threshold_without_contacting_upstream(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        request = _request(headers=[("X-Omega-Proxy-Hops", "5")])
        response = await serve_proxy(request, _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, HttpStatus.BAD_GATEWAY)
        self.assertEqual(client.calls, [])

    async def test_refuses_above_threshold(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        request = _request(headers=[("X-Omega-Proxy-Hops", "99")])
        response = await serve_proxy(request, _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, HttpStatus.BAD_GATEWAY)
        self.assertEqual(client.calls, [])

    async def test_just_below_threshold_still_proxies(self):
        client = _FakeProxyClient(result=HttpProxyResult(200, (), b""))
        request = _request(headers=[("X-Omega-Proxy-Hops", "4")])
        response = await serve_proxy(request, _zone(), client, ProxyLoadBalancerState(), ProxyHealthState())
        self.assertEqual(response.status, 200)
        self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
