import asyncio
import time
import unittest

from omega_serv.application.server.poll_upstream_load import (
    poll_upstream_load_forever,
    stop_pollers,
)
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import ProxyZone, UpstreamTarget
from omega_serv.ports.http_proxy_client_port import HttpProxyConnectionError, HttpProxyResult

_POLL_INTERVAL = 0.01


class _FakeProxyClient:
    def __init__(self, results=None, error=None):
        self._results = list(results) if results is not None else None
        self._error = error
        self.calls = []

    async def forward_request(self, host, port, method, path, headers, body, connect_timeout, read_timeout, ssl_context=None):
        self.calls.append((host, port, method, path, connect_timeout, read_timeout, ssl_context))
        if self._error is not None:
            raise self._error
        if self._results is not None:
            return self._results[min(len(self.calls), len(self._results)) - 1]
        raise AssertionError("no result configured")


def _zone(**overrides):
    defaults = {
        "url_prefix": "/api/", "upstreams": (), "load_poll_interval_seconds": _POLL_INTERVAL,
        "load_poll_timeout_seconds": 1.0,
    }
    defaults.update(overrides)
    return ProxyZone(**defaults)


async def _run_briefly_then_stop(task: asyncio.Task, *, seconds: float = 0.1) -> None:
    await asyncio.sleep(seconds)
    await stop_pollers([task])


class TestPollUpstreamLoadForever(unittest.IsolatedAsyncioTestCase):
    async def test_native_success_records_health_and_load_sample(self):
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, load_source="native")
        zone = _zone(upstreams=(upstream,))
        client = _FakeProxyClient(results=[HttpProxyResult(200, (), b'{"cpu_percent": 55.0}')])
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertEqual(health_state.status_for(zone.url_prefix, upstream), "up")
        self.assertIsNotNone(health_state.load_score_for(zone.url_prefix, upstream, max_age_seconds=60, now=time.monotonic()))
        self.assertEqual(client.calls[0][3], "/.omega-serv-load/")

    async def test_declarative_success_records_health_and_load_sample(self):
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, load_source="declarative", load_check_path="/charge")
        zone = _zone(upstreams=(upstream,))
        client = _FakeProxyClient(results=[HttpProxyResult(200, (), b"33")])
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertEqual(health_state.status_for(zone.url_prefix, upstream), "up")
        self.assertEqual(client.calls[0][3], "/charge")

    async def test_connection_error_records_failure_without_load_sample(self):
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, load_source="native")
        zone = _zone(upstreams=(upstream,), unhealthy_after=1)
        client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertEqual(health_state.status_for(zone.url_prefix, upstream), "down")

    async def test_non_2xx_status_records_failure_without_load_sample(self):
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, load_source="native")
        zone = _zone(upstreams=(upstream,), unhealthy_after=1)
        client = _FakeProxyClient(results=[HttpProxyResult(500, (), b'{"cpu_percent": 10}')])
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertEqual(health_state.status_for(zone.url_prefix, upstream), "down")

    async def test_malformed_body_keeps_health_up_but_records_no_sample(self):
        """§19.2 : un corps non interpretable n'est pas une erreur de
        connexion - la sonde a bien repondu (2xx), seul le SCORE est
        rejete, silencieusement."""
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, load_source="declarative", load_check_path="/charge")
        zone = _zone(upstreams=(upstream,))
        client = _FakeProxyClient(results=[HttpProxyResult(200, (), b"not a number")])
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertEqual(health_state.status_for(zone.url_prefix, upstream), "up")
        self.assertIsNone(health_state.load_score_for(zone.url_prefix, upstream, max_age_seconds=60, now=time.monotonic()))

    async def test_pure_health_upstream_probes_its_own_path(self):
        """§18.2 : un upstream sans `load_source` mais avec la sonde
        active activee interroge `active_health_check_path`, jamais
        `/.omega-serv-load/` ni `load_check_path` (sans effet ici)."""
        upstream = UpstreamTarget(
            host="10.0.0.1", port=3000, active_health_check_enabled=True, active_health_check_path="/healthz",
        )
        zone = _zone(upstreams=(upstream,))
        client = _FakeProxyClient(results=[HttpProxyResult(200, (), b"ok")])
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertEqual(health_state.status_for(zone.url_prefix, upstream), "up")
        self.assertEqual(client.calls[0][3], "/healthz")

    async def test_pure_health_upstream_never_records_a_load_sample(self):
        """Meme un corps qui RESSEMBLERAIT a un score valide ne doit
        jamais en produire un pour `load_source="none"` - §18.2 reste
        independant de §19."""
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, active_health_check_enabled=True)
        zone = _zone(upstreams=(upstream,))
        client = _FakeProxyClient(results=[HttpProxyResult(200, (), b"42")])
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertIsNone(health_state.load_score_for(zone.url_prefix, upstream, max_age_seconds=60, now=time.monotonic()))

    async def test_pure_health_upstream_connection_error_records_failure(self):
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, active_health_check_enabled=True)
        zone = _zone(upstreams=(upstream,), unhealthy_after=1)
        client = _FakeProxyClient(error=HttpProxyConnectionError("boom"))
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await _run_briefly_then_stop(task)
        self.assertEqual(health_state.status_for(zone.url_prefix, upstream), "down")

    async def test_task_cancels_cleanly_via_stop_pollers(self):
        upstream = UpstreamTarget(host="10.0.0.1", port=3000, load_source="native")
        zone = _zone(upstreams=(upstream,), load_poll_interval_seconds=10.0)
        client = _FakeProxyClient(results=[HttpProxyResult(200, (), b'{"cpu_percent": 1}')])
        health_state = ProxyHealthState()
        task = asyncio.create_task(poll_upstream_load_forever(zone, upstream, client, health_state, None, None))
        await asyncio.sleep(0.01)
        await asyncio.wait_for(stop_pollers([task]), timeout=2)
        self.assertTrue(task.done())
        self.assertTrue(task.cancelled())


if __name__ == "__main__":
    unittest.main()
