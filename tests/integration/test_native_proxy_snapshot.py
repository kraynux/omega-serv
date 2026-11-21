"""Plan proxy natif v2, lot 3 : le natif lit l'instantane `proxy` exactement comme Python l'ecrit (differentiel par
`--dump-proxy`), refuse une section incoherente, et confie toujours `/.omega-serv-admin/` au processus de securite
n° 0 (P6), quel que soit le fil qui a accepte la connexion.

Le binaire n'est pas versionne : sans build (native/omega-http-core/build-release), ces tests sont sautes."""
import json
import os
import select
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.native_engine import NativeEngine
from omega_serv.infrastructure.server.native_snapshot import build_native_snapshot

REPO = Path(__file__).resolve().parents[2]
BINARY = REPO / "native" / "omega-http-core" / "build-release" / "omega-http-core"

RICH_ZONES = [
    {"url_prefix": "/api/", "connect_timeout_seconds": 2.5, "read_timeout_seconds": 12, "preserve_host_header": True,
     "verify_upstream_tls": False, "load_balancing": "weighted_least_connections", "sticky_session_enabled": True,
     "sticky_cookie_name": "séance", "sticky_cookie_max_age_seconds": 60, "unhealthy_after": 4, "healthy_after": 1,
     "routing_rules": [{"header_name": "X-Tenant", "pattern": "bêta*", "upstream_key": "::1:9000"}],
     "upstreams": [{"host": "::1", "port": 9000, "weight": 2, "max_concurrent_requests": 7, "load_source": "native"},
                   {"host": "api.example", "port": 443, "use_tls": True, "load_source": "declarative"},
                   {"host": "127.1", "port": 9001}]},
    {"url_prefix": "/cache/", "cache_enabled": True, "websocket_enabled": True,
     "upstreams": [{"host": "10.0.0.5", "port": 8080}]},
]


@unittest.skipUnless(BINARY.is_file(), "binaire natif non construit")
class TestProxySnapshotDifferential(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _snapshot(self, proxy: dict | None = None, options: dict | None = None) -> dict:
        config = OmegaServConfig.from_dict({"server": {"engine": "native"}, "options": {
            **(options or {}),
            "reverse_proxy": {"enabled": True, "zones": RICH_ZONES, "max_pending_body_mb": 40,
                              "max_concurrent_inspections": 9, "max_upstream_connections": 77,
                              "max_response_body_mb": 5, **(proxy or {})}}})
        return build_native_snapshot(config, self.root, 1, security_processes=2)

    def _run(self, option: str, snapshot: dict) -> subprocess.CompletedProcess:
        path = self.root / "snapshot.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        return subprocess.run([str(BINARY), option, str(path)], capture_output=True, text=True, timeout=10, check=False)

    def test_native_reads_exactly_what_python_wrote(self):
        for proxy, options in (({}, {}), ({"engine": "python"}, {}), ({}, {"waf": {"enabled": True}})):
            snapshot = self._snapshot(proxy, options)
            result = self._run("--dump-proxy", snapshot)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), snapshot["proxy"], (proxy, options))

    def test_native_zone_read_too(self):
        # Lot 4 : une zone native n'a aucune raison - forme verifiee des maintenant.
        snapshot = self._snapshot()
        snapshot["proxy"]["zones"][0].update(engine="native", reasons=[])
        for backend in snapshot["proxy"]["zones"][0]["upstreams"]:
            if backend["address"] is None:  # lot 6 : dans une zone native, un nom resolu ou hors service (C18)
                backend["unusable"] = "dns"
        result = self._run("--dump-proxy", snapshot)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), snapshot["proxy"])

    def test_without_reverse_proxy(self):
        config = OmegaServConfig.from_dict({"server": {"engine": "native"}})
        result = self._run("--dump-proxy", build_native_snapshot(config, self.root, 1))
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "null"))

    def test_incoherent_section_refused(self):
        def broken(change) -> dict:
            snapshot = self._snapshot({"engine": "python"})  # zones confiees (auto jusqu'au lot 11)
            change(snapshot["proxy"])
            return snapshot

        cases = {
            "native avec raisons": lambda p: p["zones"][1].update(engine="native"),
            "confiee sans raison": lambda p: p["zones"][0].update(reasons=[]),
            "regle sans backend": lambda p: p["zones"][0]["routing_rules"][0].update(upstream="ailleurs:1"),
            "zone vide": lambda p: p["zones"][1].update(upstreams=[]),
            "strategie inconnue": lambda p: p["zones"][0].update(load_balancing="hasard"),
            "budget nul": lambda p: p["budgets"].update(inspections=0),
        }
        for name, change in cases.items():
            result = self._run("--check-config", broken(change))
            self.assertEqual(result.returncode, 2, name)
            self.assertIn("instantane refuse", result.stderr, name)


@unittest.skipUnless(BINARY.is_file(), "binaire natif non construit")
class TestAdminGoesToFirstSecurityProcess(unittest.TestCase):
    """P6 : avec deux processus de securite, le fil 1 est servi par le processus n° 1 ; /.omega-serv-admin/ doit
    pourtant toujours arriver au n° 0 (seul responsable de la sante). Faux processus de securite : les deux canaux
    sont lus ici. EPOLLEXCLUSIVE reveille d'abord le fil 0 : seules des rafales paralleles font accepter des
    connexions au fil 1."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "var" / "log").mkdir(parents=True)
        self.listen = socket.create_server(("127.0.0.1", 0), backlog=512)
        self.port = self.listen.getsockname()[1]

    def tearDown(self):
        self.listen.close()
        self._tmp.cleanup()

    def _burst(self, security_processes: int) -> tuple[dict, int]:
        """(trames par (canal, type), reponses 200 recues pour l'administration)."""
        config = OmegaServConfig.from_dict({"server": {"engine": "native", "port": self.port,
                                                       "max_connections": 2000}, "options": {
            "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"]},
            "reverse_proxy": {"enabled": True, "zones": [
                {"url_prefix": "/app/", "upstreams": [{"host": "10.0.0.5", "port": 8080}]}]}}})
        pairs = [ipc.data_channel_pair() for _ in range(2)]
        engine = NativeEngine(BINARY, self.root, threads=2, security_processes=security_processes)
        engine.start(config, [self.listen.fileno()], [native.fileno() for native, _worker in pairs])
        for native, _worker in pairs:
            native.close()
        ends = [worker for _native, worker in pairs]
        frames: dict[tuple[int, int], int] = {}
        admin_ok = [0]
        lock = threading.Lock()
        stop = threading.Event()

        def fake_security_processes():
            while not stop.is_set():
                ready, _, _ = select.select(ends, [], [], 0.1)
                for end in ready:
                    try:
                        frame, fd = ipc.recv_frame(end, 0.1)
                    except (TimeoutError, ipc.FrameError):
                        continue
                    if fd is not None:
                        os.close(fd)  # HANDOFF : la connexion confiee est simplement fermee
                    with lock:
                        key = (ends.index(end), frame.type)
                        frames[key] = frames.get(key, 0) + 1
                    if frame.type == ipc.INSPECT:
                        ipc.send_frame(end, ipc.verdict_frame(frame.request_id, HttpResponse.empty(HttpStatus.OK), False))

        def client(index: int):
            for n in range(30):
                path = "/.omega-serv-admin/status" if (index + n) % 2 else "/app/x"
                try:
                    with socket.create_connection(("127.0.0.1", self.port), timeout=5) as conn:
                        conn.sendall(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
                        if path.startswith("/.omega"):
                            head = conn.recv(64)
                            if head.startswith(b"HTTP/1.1 200"):
                                with lock:
                                    admin_ok[0] += 1
                except OSError:
                    pass

        reader = threading.Thread(target=fake_security_processes)
        reader.start()
        try:
            clients = [threading.Thread(target=client, args=(i,)) for i in range(8)]
            for thread in clients:
                thread.start()
            for thread in clients:
                thread.join()
        finally:
            stop.set()
            reader.join()
            engine.stop(2.0)
            for end in ends:
                end.close()
        return frames, admin_ok[0]

    def test_admin_always_reaches_process_zero(self):
        for _attempt in range(5):
            frames, admin_ok = self._burst(security_processes=2)
            if frames.get((1, ipc.HANDOFF), 0) >= 3:  # le fil 1 a bien accepte des connexions
                break
        else:
            self.skipTest("le fil 1 n'a accepte aucune connexion (machine trop peu chargee)")
        self.assertEqual(frames.get((1, ipc.INSPECT), 0), 0, frames)
        self.assertEqual(frames.get((0, ipc.INSPECT), 0), 120, frames)  # 8 clients x 15 requetes d'administration
        self.assertEqual(admin_ok, 120)

    def test_without_second_process_nothing_moves(self):
        # Garde : un seul processus de securite -> chaque fil garde ses connexions (rien n'est deplace).
        for _attempt in range(5):
            frames, admin_ok = self._burst(security_processes=1)
            if frames.get((1, ipc.HANDOFF), 0) >= 3:
                break
        else:
            self.skipTest("le fil 1 n'a accepte aucune connexion (machine trop peu chargee)")
        self.assertGreater(frames.get((1, ipc.INSPECT), 0), 0, frames)
        self.assertEqual(admin_ok, 120)


if __name__ == "__main__":
    unittest.main()
