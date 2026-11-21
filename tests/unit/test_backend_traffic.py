"""Tableau de bord par type d'instance (Projets 3.0.0 §9, chantier 3, decision de l'auteur du 2026-11-16) : type
d'instance lu dans la configuration, compteurs par backend du moteur Python, mesures envoyees par le natif, route
`/.omega-serv-admin/backends`."""
import json
import unittest

from omega_serv.application.server.serve_proxy_admin import handle_admin_request
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.proxy_backend_traffic import BackendTraffic, instance_kind
from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import ProxyLoadBalancerState, UpstreamTarget
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.relayed_health import RelayedHealthState


def _config(options: dict) -> OmegaServConfig:
    return OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 8080}, "options": options})


def _proxy(*prefixes: str, enabled: bool = True) -> dict:
    zones = [{"url_prefix": p, "upstreams": [{"host": "127.0.0.1", "port": 3000 + i}, {"host": "127.0.0.1", "port": 4000}]}
             for i, p in enumerate(prefixes)]
    return {"reverse_proxy": {"enabled": enabled, "zones": zones}}


_FASTCGI = {"fastcgi": {"enabled": True, "zones": [
    {"url_prefix": "/blog/", "script_root": "apps/blog", "socket_path": "var/run/blog.sock", "enabled": True}]}}


def _admin_get(path: str, config: OmegaServConfig, state: ProxyHealthState, balancer=None, peer="127.0.0.1"):
    request = HttpRequest(request_id="r1", remote_ip=peer, peer_ip=peer, method="GET", path=path, raw_path=path,
                          query="", headers=HttpHeaders.from_pairs([]), body=None, content_length=None, is_tls=False)
    return handle_admin_request(request, ["127.0.0.1/32"], config, state, ProxyCacheMetrics(), balancer)


class TestInstanceKind(unittest.TestCase):
    def test_four_kinds(self):
        self.assertEqual(instance_kind(_config({})), "site")
        self.assertEqual(instance_kind(_config(_FASTCGI)), "php")
        self.assertEqual(instance_kind(_config(_proxy("/"))), "proxy")
        self.assertEqual(instance_kind(_config(_proxy("/api/", "/ws/"))), "mixed")

    def test_proxy_wins_over_fastcgi_and_disabled_proxy_is_ignored(self):
        self.assertEqual(instance_kind(_config({**_proxy("/api/", "/"), **_FASTCGI})), "proxy")
        self.assertEqual(instance_kind(_config({**_proxy("/api/"), **_FASTCGI})), "mixed")
        self.assertEqual(instance_kind(_config(_proxy("/", enabled=False))), "site")
        self.assertEqual(instance_kind(_config({"reverse_proxy": {"enabled": True, "zones": []}})), "site")


class TestPythonCounters(unittest.TestCase):
    def test_requests_and_errors_per_backend(self):
        state, a = ProxyHealthState(), UpstreamTarget("127.0.0.1", 3000)
        for _ in range(3):
            state.record_request("/api/", a)
        state.record_error("/api/", a, 502)
        state.record_error("/api/", a, 504)
        self.assertEqual(state.traffic_counts("/api/", a), (3, 1, 1))
        self.assertEqual(state.traffic_counts("/autre/", a), (0, 0, 0))
        self.assertIsNone(state.relayed_traffic("/api/"))

    def test_backends_route_lists_every_backend_of_every_zone(self):
        config = _config(_proxy("/api/", "/ws/"))
        state, balancer = ProxyHealthState(), ProxyLoadBalancerState()
        a = UpstreamTarget("127.0.0.1", 3000)
        state.record_request("/api/", a)
        state.record_error("/api/", a, 502)
        state.record_failure("/api/", a, unhealthy_after=1)
        balancer.record_response_time("/api/", a, 0.25)
        balancer.acquire("/api/", a)
        response = _admin_get("/.omega-serv-admin/backends", config, state, balancer)
        self.assertEqual(response.status, HttpStatus.OK)
        rows = [BackendTraffic.from_dict(row) for row in json.loads(response.body)["backends"]]
        self.assertEqual([(r.zone, r.name) for r in rows], [("/api/", "127.0.0.1:3000"), ("/api/", "127.0.0.1:4000"),
                                                           ("/ws/", "127.0.0.1:3001"), ("/ws/", "127.0.0.1:4000")])
        first = rows[0]
        self.assertEqual((first.engine, first.status, first.requests, first.errors_502, first.errors_504, first.active),
                         ("python", "down", 1, 1, 0, 1))
        self.assertAlmostEqual(first.avg_ms, 250.0)
        self.assertIsNone(rows[1].avg_ms)

    def test_backends_route_is_guarded_and_empty_without_proxy(self):
        state = ProxyHealthState()
        refused = _admin_get("/.omega-serv-admin/backends", _config(_proxy("/")), state, peer="203.0.113.9")
        self.assertEqual(refused.status, HttpStatus.FORBIDDEN)
        empty = _admin_get("/.omega-serv-admin/backends", _config({}), state)
        self.assertEqual(json.loads(empty.body), {"backends": []})

    def test_unreadable_entry_is_skipped(self):
        self.assertIsNone(BackendTraffic.from_dict({"zone": "/api/"}))
        self.assertIsNone(BackendTraffic.from_dict({"zone": "/", "name": "a", "status": "up", "requests": "x"}))


class TestNativeMeasures(unittest.TestCase):
    def test_frame_carries_counters_and_old_frames_still_read(self):
        frame = ipc.Frame(ipc.BACKEND_STATE)
        for fields in (("/api/", "k", "n", "up", "2", "1500", "3", "1", "12500"),
                       ("/api/", "k2", "n", "down", "0", "0", "0", "0", "-1"),
                       ("/api/", "old", "n", "up", "3"),
                       ("/api/", "bad", "n", "up", "x", "1", "2", "3", "4")):
            frame.add(ipc.BACKEND_ENTRY, "\0".join(fields))
        self.assertEqual(ipc.backend_states(ipc.decode(ipc.encode(frame))), [
            ("/api/", "k", "n", "up", 2, 1500, 3, 1, 12500), ("/api/", "k2", "n", "down", 0, 0, 0, 0, -1),
            ("/api/", "old", "n", "up", 3)])

    def test_relayed_zone_gives_one_row_per_address(self):
        config = _config({**_proxy("/api/"), "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"]}})
        state = RelayedHealthState(lambda entries: None, lambda: frozenset({"/api/"}))
        state.apply_report([("/api/", "api (10.0.0.7):3000", "127.0.0.1:3000", "up", 1, 40, 2, 1, 12500),
                            ("/api/", "127.0.0.1:4000", "127.0.0.1:4000", "down", 0, 3, 3, 0, -1),
                            ("/autre/", "x:1", "x:1", "up", 0)])  # natif plus ancien : 5 champs
        rows = [BackendTraffic.from_dict(r) for r in
                json.loads(_admin_get("/.omega-serv-admin/backends", config, state).body)["backends"]]
        self.assertEqual(len(rows), 2)
        first, second = rows
        self.assertEqual((first.name, first.address, first.engine, first.requests, first.errors_502, first.errors_504,
                          first.active), ("127.0.0.1:3000", "api (10.0.0.7):3000", "natif", 40, 2, 1, 1))
        self.assertAlmostEqual(first.avg_ms, 12.5)
        self.assertEqual((second.status, second.avg_ms), ("down", None))
        self.assertEqual(state.relayed_traffic("/autre/"), None)  # zone confiee a Python


if __name__ == "__main__":
    unittest.main()
