# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 6 : equilibrage dans le relais natif - instantane (un backend par adresse d'un nom DNS,
resolution gardee, boucle exclue), processus de securite n° 0 (sondes, etats manuels et scores vers le natif, etat des
backends en retour pour l'administration), WATCH porte par le verdict (P5, S26), capacite exigee du binaire."""
import asyncio
import socket
import unittest

from omega_serv.application.server.engine_selection import decide_proxy_zones, native_zone_prefixes
from omega_serv.application.server.serve_proxy_admin import handle_admin_request
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
from omega_serv.domain.routing.proxy_zone import (
    UpstreamTarget,
    sticky_cookie_value_for,
    sticky_cookie_value_for_key,
)
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server import native_snapshot
from omega_serv.infrastructure.server.native_engine import required_capabilities
from omega_serv.infrastructure.server.relayed_health import RelayedHealthState
from omega_serv.infrastructure.server.security_worker import SecurityWorker


def _config(upstreams, engine="native", port=8080, **zone):
    return OmegaServConfig.from_dict({"server": {"engine": "native", "port": port, "bind": "127.0.0.1"}, "options": {
        "reverse_proxy": {"enabled": True, "engine": engine,
                          "zones": [{"url_prefix": "/api/", "upstreams": upstreams, **zone}]}}})


def _frames(sock: socket.socket) -> list[ipc.Frame]:
    sock.setblocking(False)
    frames = []
    while True:
        try:
            frames.append(ipc.decode(sock.recv(ipc.HEADER_SIZE + ipc.MAX_PAYLOAD)))
        except BlockingIOError:
            return frames


class TestSnapshotBackends(unittest.TestCase):
    def setUp(self):
        native_snapshot._LAST_RESOLVED.clear()
        self.addCleanup(native_snapshot._LAST_RESOLVED.clear)

    def _section(self, config, resolved):
        notes: list[str] = []
        section = native_snapshot.proxy_section(config, False, None, lambda hosts: dict(resolved), notes)
        return section["zones"][0], notes

    def test_ip_backend_keeps_the_python_key_and_cookie(self):
        zone, notes = self._section(_config([{"host": "10.0.0.5", "port": 9000}]), {})
        (backend,) = zone["upstreams"]
        self.assertEqual((backend["key"], backend["name"], backend["address"], backend["unusable"]),
                         ("10.0.0.5:9000", "10.0.0.5:9000", "10.0.0.5", None))
        self.assertEqual(backend["cookie"], sticky_cookie_value_for(UpstreamTarget("10.0.0.5", 9000)))
        self.assertEqual(notes, [])

    def test_dns_name_gives_one_backend_per_address(self):
        config = _config([{"host": "api.example", "port": 9000, "weight": 3, "max_concurrent_requests": 4}])
        self.assertEqual(decide_proxy_zones(config)[0].engine, "native")  # lot 6 : plus une lacune
        zone, notes = self._section(config, {"api.example": ("10.0.0.7", "2001:db8::7")})
        keys = [b["key"] for b in zone["upstreams"]]
        self.assertEqual(keys, ["api.example (10.0.0.7):9000", "api.example (2001:db8::7):9000"])
        for backend in zone["upstreams"]:  # decision de l'auteur : poids, plafond, cookie par adresse
            self.assertEqual((backend["name"], backend["weight"], backend["max_concurrent"], backend["host_header"]),
                             ("api.example:9000", 3, 4, "api.example:9000"))
            self.assertEqual(backend["cookie"], sticky_cookie_value_for_key(backend["key"]))
        self.assertEqual(notes, ["reverse proxy : api.example:9000 résolu en 10.0.0.7, 2001:db8::7 (zone /api/)"])

    def test_failed_resolution_keeps_previous_addresses_or_is_out_of_service(self):
        config = _config([{"host": "api.example", "port": 9000}, {"host": "10.0.0.5", "port": 9000}])
        zone, notes = self._section(config, {})  # premier demarrage : jamais resolu
        self.assertEqual([(b["key"], b["address"], b["unusable"]) for b in zone["upstreams"]],
                         [("api.example:9000", None, "dns"), ("10.0.0.5:9000", "10.0.0.5", None)])
        self.assertIn("backend hors service", notes[0])
        self._section(config, {"api.example": ("10.0.0.7",)})
        zone, notes = self._section(config, {})  # rechargement sans DNS : adresses precedentes gardees
        self.assertEqual(zone["upstreams"][0]["address"], "10.0.0.7")
        self.assertIn("adresses précédentes gardées (10.0.0.7)", notes[0])

    def test_address_of_this_server_is_a_loop(self):
        zone, notes = self._section(_config([{"host": "api.example", "port": 8080}]), {"api.example": ("127.0.0.1",)})
        self.assertEqual(zone["upstreams"][0]["unusable"], "boucle")
        self.assertIn("boucle", notes[-1])

    def test_handed_off_zone_is_never_resolved(self):
        calls = []
        native_snapshot.proxy_section(_config([{"host": "api.example", "port": 9000}], engine="python"), False, None,
                                      lambda hosts: calls.append(list(hosts)) or {}, [])
        self.assertEqual(calls, [])

    def test_config_check_warns_for_an_unresolved_name(self):
        from omega_serv.application.config.validate_config import config_problems
        config = _config([{"host": "api.example", "port": 9000}, {"host": "10.0.0.5", "port": 9000}])
        warnings = config_problems(config, (), resolve_names=True, resolver=lambda names: {}).warnings
        self.assertEqual(len([w for w in warnings if "ne se résout pas" in w.text]), 1)
        resolved = config_problems(config, (), resolve_names=True, resolver=lambda names: {"api.example": ("10.0.0.7",)})
        self.assertFalse([w for w in resolved.warnings if "ne se résout pas" in w.text])

    def test_binary_must_balance(self):
        self.assertIn("proxy_balance", required_capabilities(_config([{"host": "10.0.0.5", "port": 9000}])))
        # zone confiee (engine = python ; auto jusqu'au lot 11) : aucun relais natif a demander
        self.assertNotIn("proxy_balance", required_capabilities(_config([{"host": "10.0.0.5", "port": 9000}], "python")))


class _Server:
    watch_sink = None
    probe_filter = None

    def __init__(self, config=None):
        self.config = config
        self.state = None

    def replace_proxy_health_state(self, state):
        self.state = state


class TestFirstSecurityProcess(unittest.TestCase):
    def setUp(self):
        self.ours, self.native = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.addCleanup(self.ours.close)
        self.addCleanup(self.native.close)
        self.config = _config([{"host": "10.0.0.5", "port": 9000}, {"host": "10.0.0.6", "port": 9000}])

    def test_only_the_first_process_probes_native_zones(self):
        first, other = _Server(self.config), _Server(self.config)
        SecurityWorker(first, [self.ours], first=True)
        SecurityWorker(other, [self.ours])
        self.assertTrue(first.probe_filter("/api/"))
        self.assertFalse(other.probe_filter("/api/"))
        self.assertTrue(other.probe_filter("/confiee/"))  # zone confiee : chaque processus la sert et la sonde
        self.assertIsInstance(first.state, RelayedHealthState)
        self.assertIsNone(other.state)

    def test_probes_manual_states_and_scores_go_to_the_native_engine(self):
        server = _Server(self.config)
        SecurityWorker(server, [self.ours], first=True)
        state, upstream = server.state, UpstreamTarget("10.0.0.5", 9000)
        state.record_failure("/api/", upstream, unhealthy_after=3)
        state.record_success("/api/", upstream, healthy_after=2)
        state.record_load_sample("/api/", upstream, 40.0, smoothing_samples=2, now=1.0)
        state.record_load_sample("/api/", upstream, 60.0, smoothing_samples=2, now=2.0)
        state.mark_draining("/api/", "10.0.0.5:9000")
        state.record_failure("/autre/", upstream, unhealthy_after=3)  # zone inconnue du natif : rien
        entries = [entry for frame in _frames(self.native) for entry in frame.all(ipc.BACKEND_ENTRY)]
        self.assertEqual(entries, [b"/api/\x0010.0.0.5:9000\x00probe\x00fail", b"/api/\x0010.0.0.5:9000\x00probe\x00ok",
                                   b"/api/\x0010.0.0.5:9000\x00load\x0040.0", b"/api/\x0010.0.0.5:9000\x00load\x0050.0",
                                   b"/api/\x0010.0.0.5:9000\x00manual\x00draining"])

    def test_administration_reads_the_native_state(self):
        server = _Server(self.config)
        SecurityWorker(server, [self.ours], first=True)
        server.state.apply_report([("/api/", "10.0.0.5:9000", "10.0.0.5:9000", "down", 0),
                                   ("/api/", "10.0.0.6:9000", "10.0.0.6:9000", "up", 2)])
        request = type("R", (), {"peer_ip": "127.0.0.1", "path": "/.omega-serv-admin/health", "query": "zone=/api/",
                                 "method": "GET", "headers": ()})()
        response = handle_admin_request(request, ["127.0.0.1"], self.config, server.state, ProxyCacheMetrics())
        import json
        payload = json.loads(response.body)
        self.assertEqual(payload["upstreams"], {"10.0.0.5:9000": "down", "10.0.0.6:9000": "up"})
        self.assertEqual(payload["backends"], {"10.0.0.5:9000": "down", "10.0.0.6:9000": "up"})

    def test_dns_name_status_aggregates_its_addresses(self):
        state = RelayedHealthState(lambda entries: None, lambda: frozenset({"/api/"}))
        name = UpstreamTarget("api.example", 9000)
        state.apply_report([("/api/", "api.example (10.0.0.7):9000", "api.example:9000", "down", 0),
                            ("/api/", "api.example (10.0.0.8):9000", "api.example:9000", "up", 0)])
        self.assertEqual(state.status_for("/api/", name), "up")  # une adresse saine suffit
        state.apply_report([("/api/", "api.example (10.0.0.7):9000", "api.example:9000", "down", 0)])
        self.assertEqual(state.status_for("/api/", name), "down")
        state.mark_maintenance("/api/", "api.example:9000")
        self.assertEqual(state.status_for("/api/", name), "maintenance")  # vrai tout de suite, avant le rapport

    def test_native_zone_prefixes(self):
        self.assertEqual(native_zone_prefixes(self.config), frozenset({"/api/"}))
        self.assertEqual(native_zone_prefixes(_config([{"host": "10.0.0.5", "port": 9000}], "python")), frozenset())
        # lot 11 : auto rend la zone native
        self.assertEqual(native_zone_prefixes(_config([{"host": "10.0.0.5", "port": 9000}], "auto")),
                         frozenset({"/api/"}))


class _WatchingServer:
    watch_sink = None
    probe_filter = None
    config = None

    def build_request(self, head, peer_ip, request_id, body=None, client_ip=None):
        return type("R", (), {"method": head.method, "path": head.target, "remote_ip": peer_ip})()

    async def security_stage(self, request, blocklist_known_clear=False, native_rate_limit=None):
        from omega_serv.infrastructure.server.asyncio_server import SecurityOutcome
        self.watch_sink("203.0.113.4", 5000.2)  # cette requete fait surveiller sa source
        return SecurityOutcome(None, notable=True)


class TestWatchCarriedByTheVerdict(unittest.TestCase):
    def test_watch_decided_during_inspection_rides_on_the_verdict(self):
        ours, native = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.addCleanup(ours.close)
        self.addCleanup(native.close)
        worker = SecurityWorker(_WatchingServer(), [ours])
        frame = (ipc.Frame(ipc.INSPECT, request_id=7).add(ipc.INSPECT_PEER, "203.0.113.4").add(ipc.INSPECT_METHOD, "GET")
                 .add(ipc.INSPECT_TARGET, "/x").add(ipc.INSPECT_VERSION, "HTTP/1.1"))
        asyncio.run(worker._inspect(ours, frame))
        frames = _frames(native)
        self.assertEqual([f.type for f in frames], [ipc.VERDICT])  # P5 : aucune trame WATCH a part
        self.assertEqual(frames[0].all(ipc.VERDICT_WATCH), [b"203.0.113.4\x005001"])
        self.assertEqual(frames[0].uint(ipc.VERDICT_DECISION), ipc.CONTINUE)
        worker._watch("203.0.113.9", 6000.0)  # hors inspection (RIPOSTE, resynchronisation) : trame WATCH
        self.assertEqual([f.type for f in _frames(native)], [ipc.WATCH])

    def test_ipc_helpers(self):
        frame = ipc.Frame(ipc.BACKEND_STATE).add(ipc.BACKEND_ENTRY, "/api/\x00k\x00n\x00up\x003")
        frame.add(ipc.BACKEND_ENTRY, "illisible")
        self.assertEqual(ipc.backend_states(ipc.decode(ipc.encode(frame))), [("/api/", "k", "n", "up", 3)])


if __name__ == "__main__":
    unittest.main()
