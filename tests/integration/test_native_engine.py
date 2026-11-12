"""Pilote du moteur natif (plan moteur C++ lot 3) : vrai binaire omega-http-core sur une socket ouverte par le
superviseur, generations, sante, arret ; faux binaires pour chaque cause de repli au demarrage (contrat
different, arret immediat, silence, configuration refusee) ; superviseur `serve` complet (repli si binaire absent,
natif qui s'arrete seul si le superviseur disparait).

Le binaire n'est pas versionne : sans build (native/omega-http-core/build-release), ces tests sont sautes."""
import http.client
import json
import os
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from omega_serv.application.server.engine_levels import max_workers
from omega_serv.core.platform_info import cpu_info
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.server import native_engine as native_engine_module
from omega_serv.infrastructure.server.native_engine import (
    CONFIG_REFUSED,
    CONTRACT_MISMATCH,
    EXITED,
    NO_HELLO,
    NativeEngine,
    NativeStartError,
)

REPO = Path(__file__).resolve().parents[2]
BINARY = REPO / "native" / "omega-http-core" / "build-release" / "omega-http-core"
PYTHON = sys.executable


def _fake_binary(folder: Path, body: str) -> Path:
    """Faux moteur : script Python qui parle (mal) le contrat, pour chaque cause de repli."""
    path = folder / "fake-engine"
    path.write_text(f"#!{PYTHON}\n" + textwrap.dedent(f"""
        import os, socket, sys, time
        sys.path.insert(0, {str(REPO / "src")!r})
        from omega_serv.infrastructure.server import native_ipc as ipc
        fd = int(sys.argv[sys.argv.index("--control-fd") + 1])
        channel = socket.socket(fileno=fd)
    """) + textwrap.dedent(body))
    path.chmod(0o755)
    return path


class _Project:
    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("bonjour natif")
        (self.root / "var" / "log").mkdir(parents=True)
        (self.root / "var" / "run").mkdir(parents=True)

    def cleanup(self) -> None:
        self._tmp.cleanup()


@unittest.skipUnless(BINARY.is_file(), "binaire natif non construit")
class TestNativeEngine(unittest.TestCase):
    def setUp(self):
        self.project = _Project()
        self.listen = socket.create_server(("127.0.0.1", 0))
        self.port = self.listen.getsockname()[1]
        self.config = OmegaServConfig.from_dict({"server": {"engine": "native", "port": self.port}})

    def tearDown(self):
        self.listen.close()
        self.project.cleanup()

    def _get(self, path: str) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_handshake_serve_reload_health_and_stop(self):
        engine = NativeEngine(BINARY, self.project.root, threads=2)
        engine.start(self.config, [self.listen.fileno()])
        try:
            self.assertEqual(engine.generation, 1)
            self.assertTrue(engine.binary_version)
            self.assertEqual(self._get("/"), (200, b"bonjour natif"))

            reloaded = OmegaServConfig.from_dict({"server": {"engine": "native", "port": self.port}, "options": {
                "redirects": {"enabled": True, "list": [{"url_prefix": "/old", "destination": "/"}]}}})
            self.assertIsNone(engine.reload(reloaded))
            self.assertEqual(engine.generation, 2)
            self.assertEqual(self._get("/old")[0], 302)

            engine.pump(2.5)  # au moins un battement de sante (1 s)
            self.assertEqual(engine.health.generation, 2)
            self.assertGreaterEqual(engine.health.requests, 2)
        finally:
            status = engine.stop(2.0)
        self.assertEqual(status, 0)
        self.assertFalse(engine.alive())

    def _tls_config(self) -> OmegaServConfig:
        certs = self.project.root / "certs"
        certs.mkdir()
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                        "-keyout", str(certs / "key.pem"), "-out", str(certs / "cert.pem"), "-days", "2",
                        "-subj", "/CN=localhost"], check=True, capture_output=True)
        return OmegaServConfig.from_dict({"server": {"engine": "native", "port": self.port},
                                          "security": {"hsts_enabled": True}, "tls": {
            "enabled": True, "mode": "direct",
            "certificate": {"certificate_path": "certs/cert.pem", "private_key_path": "certs/key.pem"}}})

    def test_direct_tls_served_natively(self):
        # Lot 3b : TLS direct par le natif (OpenSSL, meme contexte que ssl_context_builder.py).
        engine = NativeEngine(BINARY, self.project.root, threads=2)
        engine.start(self._tls_config(), [self.listen.fileno()])
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            conn = http.client.HTTPSConnection("127.0.0.1", self.port, timeout=3, context=context)
            conn.request("GET", "/")
            response = conn.getresponse()
            self.assertEqual((response.status, response.read()), (200, b"bonjour natif"))
            self.assertIn("Strict-Transport-Security", dict(response.getheaders()))  # HSTS active + TLS actif
            conn.close()
        finally:
            engine.stop(2.0)

    def test_unusable_certificate_never_falls_back_to_plain_http(self):
        config = self._tls_config()
        (self.project.root / "certs" / "key.pem").write_text("pas une cle\n")
        engine = NativeEngine(BINARY, self.project.root)
        with self.assertRaises(NativeStartError) as ctx:
            engine.start(config, [self.listen.fileno()])
        self.assertEqual(ctx.exception.code, CONFIG_REFUSED)
        self.assertIn("TLS", ctx.exception.detail)
        self.assertFalse(engine.alive())

    def test_security_unavailable_follows_on_internal_error_and_auth_always_refuses(self):
        # Lot 4 : sans processus de securite, waf.on_internal_error decide ; une zone Auth active = toujours 503.
        rules = self.project.root / "rules.json"
        shutil.copy(next(p for p in sorted((REPO / "secure" / "waf" / "rules").glob("*.json")) if p.name != "custom.json"), rules)
        waf = {"enabled": True, "rules": {"paths": [str(rules)]}}
        for options, expected in (({"waf": {**waf, "on_internal_error": "fail-open"}}, 200),
                                  ({"waf": {**waf, "on_internal_error": "fail-closed"}}, 503),
                                  ({"waf": {**waf, "on_internal_error": "fail-open"}, "auth": {"enabled": True}}, 503)):
            with self.subTest(options=options):
                # socket neuve : l'arret precedent a ferme l'ecoute (shutdown) de la socket partagee
                self.listen.close()
                self.listen = socket.create_server(("127.0.0.1", 0))
                self.port = self.listen.getsockname()[1]
                config = OmegaServConfig.from_dict({"server": {"engine": "native", "port": self.port}, "options": options})
                engine = NativeEngine(BINARY, self.project.root, threads=1)
                engine.start(config, [self.listen.fileno()])  # aucun canal de securite
                try:
                    self.assertEqual(self._get("/")[0], expected)
                finally:
                    engine.stop(2.0)
        errors = (self.project.root / "var" / "log" / "error.log").read_text()
        self.assertIn("controle de securite indisponible (aucun canal) : requete servie sans controle (fail-open)", errors)
        self.assertIn("refusee (503, fail-closed)", errors)

    def test_fail_open_never_frees_a_banned_address(self):
        # Decision utilisateur 2026-11-02 : sans controle de securite (fail-open), un banni reste refuse en 451.
        rules = self.project.root / "rules.json"
        shutil.copy(next(p for p in sorted((REPO / "secure" / "waf" / "rules").glob("*.json")) if p.name != "custom.json"), rules)
        blocklist = self.project.root / "var" / "lib" / "waf" / "blocklist.json"
        blocklist.parent.mkdir(parents=True)

        def ban(network: str) -> None:
            blocklist.write_text(json.dumps({"version": 1, "entries": [{
                "network": network, "reason": "test", "created_at": "2026-11-02T00:00:00+00:00",
                "expires_at": None, "source": "manual"}]}))

        config = OmegaServConfig.from_dict({"server": {"engine": "native", "port": self.port}, "options": {
            "waf": {"enabled": True, "on_internal_error": "fail-open", "rules": {"paths": [str(rules)]}}}})
        ban("127.0.0.1/32")
        engine = NativeEngine(BINARY, self.project.root, threads=1)
        engine.start(config, [self.listen.fileno()])  # aucun canal de securite
        try:
            self.assertEqual(self._get("/")[0], 451)
            ban("198.51.100.0/24")
            time.sleep(1.2)  # relu au plus une fois par seconde
            self.assertEqual(self._get("/")[0], 200)  # plus banni : servi sans controle (fail-open)
        finally:
            engine.stop(2.0)
        self.assertIn("adresse bannie refusee par le moteur natif (451)",
                      (self.project.root / "var" / "log" / "error.log").read_text())

    def test_contract_mismatch_refused(self):
        fake = _fake_binary(self.project.root, """
            ipc.send_frame(channel, ipc.Frame(ipc.HELLO).add_uint(ipc.HELLO_CONTRACT, 99, 2))
            ack, _ = ipc.recv_frame(channel, 5)
            sys.exit(0 if ack.uint(ipc.ACK_ACCEPTED) == 0 else 9)
        """)
        engine = NativeEngine(fake, self.project.root)
        with self.assertRaises(NativeStartError) as ctx:
            engine.start(self.config, [self.listen.fileno()])
        self.assertEqual(ctx.exception.code, CONTRACT_MISMATCH)
        self.assertFalse(engine.alive())

    def test_missing_capability_refused(self):
        fake = _fake_binary(self.project.root, """
            ipc.send_frame(channel, ipc.Frame(ipc.HELLO).add_uint(ipc.HELLO_CONTRACT, 1, 2).add(ipc.HELLO_CAPABILITY, "static"))
            ipc.recv_frame(channel, 5)
        """)
        engine = NativeEngine(fake, self.project.root)
        with self.assertRaises(NativeStartError) as ctx:
            engine.start(self.config, [self.listen.fileno()])
        self.assertIn("access_log", ctx.exception.detail)

    def test_engine_that_exits_immediately(self):
        engine = NativeEngine(_fake_binary(self.project.root, "sys.exit(4)\n"), self.project.root)
        with self.assertRaises(NativeStartError) as ctx:
            engine.start(self.config, [self.listen.fileno()])
        self.assertEqual(ctx.exception.code, EXITED)

    def test_silent_engine_times_out_and_is_killed(self):
        native_engine_module.HELLO_TIMEOUT_SECONDS, saved = 0.5, native_engine_module.HELLO_TIMEOUT_SECONDS
        try:
            engine = NativeEngine(_fake_binary(self.project.root, "time.sleep(60)\n"), self.project.root)
            with self.assertRaises(NativeStartError) as ctx:
                engine.start(self.config, [self.listen.fileno()])
        finally:
            native_engine_module.HELLO_TIMEOUT_SECONDS = saved
        self.assertEqual(ctx.exception.code, NO_HELLO)
        self.assertFalse(engine.alive())

    def test_refused_config_is_a_start_failure(self):
        caps = "".join(f'.add(ipc.HELLO_CAPABILITY, "{c}")' for c in ("static", "range", "precompressed", "access_log", "security_headers"))
        fake = _fake_binary(self.project.root, f"""
            ipc.send_frame(channel, ipc.Frame(ipc.HELLO).add_uint(ipc.HELLO_CONTRACT, 1, 2){caps})
            ipc.recv_frame(channel, 5)
            config, memfd = ipc.recv_frame(channel, 5)
            os.close(memfd)
            ipc.send_frame(channel, ipc.Frame(ipc.CONFIG_ACK, generation=config.generation)
                           .add_uint(ipc.CONFIG_OK, 0, 1).add(ipc.CONFIG_ERROR, "instantane refuse : test"))
            time.sleep(30)
        """)
        engine = NativeEngine(fake, self.project.root)
        with self.assertRaises(NativeStartError) as ctx:
            engine.start(self.config, [self.listen.fileno()])
        self.assertEqual(ctx.exception.code, CONFIG_REFUSED)
        self.assertIn("instantane refuse : test", ctx.exception.detail)
        self.assertFalse(engine.alive())


@unittest.skipUnless(BINARY.is_file(), "binaire natif non construit")
class TestServeSupervisor(unittest.TestCase):
    """`omega-serv serve` reel, dans un projet temporaire. La racine du projet est deduite de l'emplacement REEL du
    paquet (bootstrap/paths.py, `resolve()` suit les liens) : src/ est COPIE dans le projet, une fois pour la
    classe (comme tools/differential), sinon le serveur ecrirait dans le vrai var/ du depot (constate le
    2026-11-02 pendant l'ecriture de ce test)."""

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.root = Path(cls.shared.name)
        shutil.copytree(REPO / "src", cls.root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.bak"))

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        for folder in ("var", "bin", "webroot", "config", "secure"):
            shutil.rmtree(self.root / folder, ignore_errors=True)
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("bonjour natif")
        (self.root / "var" / "log").mkdir(parents=True)
        (self.root / "var" / "run").mkdir(parents=True)
        self.real_state = REPO / "var" / "run" / "engine-state.json"
        self.real_state_existed = self.real_state.exists()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        (self.root / "config").mkdir()
        (self.root / "config" / "omega-serve.json").write_text(json.dumps(
            {"server": {"engine": "native", "port": self.port}}))
        self.process: subprocess.Popen[bytes] | None = None

    def tearDown(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(5)
        self.assertEqual(self.real_state.exists(), self.real_state_existed, "ecriture dans le vrai var/ du depot")

    def _serve(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(self.root / "src")}
        self.process = subprocess.Popen(
            [PYTHON, "-m", "omega_serv", "--config", "config/omega-serve.json", "serve"],
            cwd=self.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        time.sleep(0.5)  # premier etat ecrit

    def _state(self) -> dict:
        return json.loads((self.root / "var" / "run" / "engine-state.json").read_text())

    def test_missing_binary_falls_back_to_python_and_says_why(self):
        self._serve()  # pas de bin/omega-http-core dans ce projet
        state = self._state()
        self.assertEqual((state["requested"], state["effective"]), ("native", "python"))
        self.assertIn("binary_missing", state["reasons"])
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/")
        self.assertEqual(conn.getresponse().status, 200)
        conn.close()
        assert self.process is not None
        self.process.send_signal(signal.SIGTERM)
        output = self.process.communicate(timeout=15)[0].decode()
        self.assertIn("moteur natif demande mais non utilisable", output)
        self.assertIn("binaire natif absent", (self.root / "var" / "log" / "error.log").read_text())

    def test_native_serves_and_stops_when_supervisor_dies(self):
        (self.root / "bin").mkdir()
        (self.root / "bin" / "omega-http-core").symlink_to(BINARY)
        self._serve()
        state = self._state()
        self.assertEqual(state["effective"], "native")
        native_pid = state["native_pid"]
        assert self.process is not None
        self.process.kill()  # superviseur tue brutalement
        self.process.wait(5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(native_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            os.kill(native_pid, signal.SIGKILL)
            self.fail("le moteur natif a survecu a son superviseur")


    def test_security_process_blocks_and_is_restarted(self):
        # Lot 4 : blocklist (WAF) servie par le processus de securite ; tue, il est relance et bloque toujours.
        waf_state = self.root / "var" / "lib" / "waf"
        waf_state.mkdir(parents=True)
        (waf_state / "blocklist.json").write_text(json.dumps({"version": 1, "entries": [{
            "network": "203.0.113.66/32", "reason": "test", "created_at": "2026-11-02T00:00:00+00:00",
            "expires_at": None, "source": "manual"}]}))
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        pack = next(p for p in sorted((REPO / "secure" / "waf" / "rules").glob("*.json")) if p.name != "custom.json")
        shutil.copy(pack, rules / pack.name)
        (self.root / "config" / "omega-serve.json").write_text(json.dumps({
            "server": {"engine": "native", "port": self.port},
            "options": {"waf": {"enabled": True, "mode": "block", "rules": {"paths": [f"secure/waf/rules/{pack.name}"]}},
                        "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1"],
                                          "header_preference": ["X-Forwarded-For"]}}}))
        (self.root / "bin").mkdir()
        (self.root / "bin" / "omega-http-core").symlink_to(BINARY)
        self._serve()

        def status(ip: str) -> int:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            conn.request("GET", "/", headers={"X-Forwarded-For": ip})
            code = conn.getresponse().status
            conn.close()
            return code

        if not (self.root / "var" / "run" / "engine-state.json").exists():
            assert self.process is not None
            self.process.kill()
            self.fail(self.process.communicate(timeout=5)[0].decode())
        state = self._state()
        self.assertEqual(state["effective"], "native")
        self.assertEqual((status("203.0.113.66"), status("198.51.100.1")), (451, 200))
        first = int(state["extra"]["security_pid"])
        os.kill(first, signal.SIGKILL)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            second = self._state()["extra"].get("security_pid", "")
            if second and int(second) != first:
                break
            time.sleep(0.2)
        else:
            self.fail("processus de securite non relance")
        self.assertEqual((status("203.0.113.66"), status("198.51.100.1")), (451, 200))
        alerts = (self.root / "var" / "log" / "waf-alerts.log").read_text()
        self.assertEqual(alerts.count("203.0.113.66"), 2)  # journaux de securite ecrits par Python, comme avant


    def test_blocklist_change_seen_on_next_request(self):
        # Lot 8 : le natif dit « non bannie » a Python seulement sur l'etat ACTUEL du fichier - un ban ajoute en
        # cours de route (RIPOSTE, omega-jail, CLI) s'applique des la requete suivante, alerte ecrite par Python.
        waf_state = self.root / "var" / "lib" / "waf"
        waf_state.mkdir(parents=True)
        blocklist = waf_state / "blocklist.json"

        def write_bans(*networks: str) -> None:
            temporary = blocklist.with_suffix(".tmp")
            temporary.write_text(json.dumps({"version": 1, "entries": [{
                "network": n, "reason": "test lot 8", "created_at": "2026-11-03T00:00:00+00:00",
                "expires_at": None, "source": "manual"} for n in networks]}))
            temporary.replace(blocklist)  # comme atomic_write_text

        write_bans()
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        pack = next(p for p in sorted((REPO / "secure" / "waf" / "rules").glob("*.json")) if p.name != "custom.json")
        shutil.copy(pack, rules / pack.name)
        (self.root / "config" / "omega-serve.json").write_text(json.dumps({
            "server": {"engine": "native", "port": self.port},
            "options": {"waf": {"enabled": True, "mode": "block", "rules": {"paths": [f"secure/waf/rules/{pack.name}"]}},
                        "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1"],
                                          "header_preference": ["X-Forwarded-For"]}}}))
        (self.root / "bin").mkdir()
        (self.root / "bin" / "omega-http-core").symlink_to(BINARY)
        self._serve()
        self.assertEqual(self._state()["effective"], "native")

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)

        def status(ip: str) -> int:
            conn.request("GET", "/", headers={"X-Forwarded-For": ip})
            response = conn.getresponse()
            response.read()
            return response.status

        self.assertEqual(status("203.0.113.66"), 200)
        write_bans("203.0.113.66/32")
        self.assertEqual(status("203.0.113.66"), 451)  # sans aucun delai
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.assertEqual(status("198.51.100.1"), 200)
        write_bans()
        self.assertEqual(status("203.0.113.66"), 200)
        conn.close()
        alerts = (self.root / "var" / "log" / "waf-alerts.log").read_text()
        self.assertEqual(alerts.count("203.0.113.66"), 1)
        self.assertIn('"stage": "blocklist"', alerts)

    def test_application_routes_are_handed_off_to_python(self):
        # Lot 6 : reverse proxy et envoi de fichiers -> connexion confiee a Python, qui la garde jusqu'au bout.
        import http.server
        import threading

        class Upstream(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"reponse amont " + self.path.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        self.addCleanup(upstream.shutdown)
        (self.root / "config" / "omega-serve.json").write_text(json.dumps({
            "server": {"engine": "native", "port": self.port},
            "security": {"allowed_methods": ["GET", "HEAD", "POST"]},
            "options": {
                "reverse_proxy": {"enabled": True, "zones": [{
                    "url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": upstream.server_address[1]}],
                    "connect_timeout_seconds": 2, "read_timeout_seconds": 2}]},
                "upload": {"enabled": True, "zones": [{"url_prefix": "/upload", "storage_path": "var/uploads"}]},
            }}))
        (self.root / "bin").mkdir()
        (self.root / "bin" / "omega-http-core").symlink_to(BINARY)
        self._serve()
        self.assertEqual(self._state()["effective"], "native")

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/")                      # natif
        first = conn.getresponse()
        self.assertEqual((first.status, first.read()), (200, b"bonjour natif"))
        conn.request("GET", "/api/x?y=1")             # confiee a Python -> amont
        second = conn.getresponse()
        self.assertEqual((second.status, second.read()), (200, b"reponse amont /api/x?y=1"))
        conn.request("GET", "/")                      # Python garde la connexion
        third = conn.getresponse()
        self.assertEqual((third.status, third.read()), (200, b"bonjour natif"))
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = b"x" * 900_000  # plus gros que la trame : octets deja lus transmis par memfd
        boundary = "frontiere-omega"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"gros.bin\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode() + payload + f"\r\n--{boundary}--\r\n".encode()
        conn.request("POST", "/upload", body=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        upload = conn.getresponse()
        upload.read()
        conn.close()
        self.assertLess(upload.status, 300)
        stored = [p for p in (self.root / "var" / "uploads").rglob("*") if p.is_file()]
        self.assertTrue(any(p.stat().st_size == len(payload) for p in stored), stored)

        access = (self.root / "var" / "log" / "access.log").read_text()
        self.assertEqual(access.count('"GET / HTTP/1.1" 200'), 2)  # une ligne natif, une ligne Python
        self.assertIn('"GET /api/x?y=1 HTTP/1.1" 200', access)
        self.assertIn('"POST /upload HTTP/1.1"', access)

    def test_hyperboost_shares_rate_limit_counters_between_security_processes(self):
        # Lot 7 : server.workers = 2 -> deux processus de securite ; compteurs partages (comme le mode boost) :
        # une politique de 3 requetes laisse passer exactement 3 requetes, quel que soit le processus qui juge.
        # Plan §25 : 2 seulement a partir de 4 coeurs physiques ; en dessous, ramene a 1 avec un message.
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        pack = next(p for p in sorted((REPO / "secure" / "waf" / "rules").glob("*.json")) if p.name != "custom.json")
        shutil.copy(pack, rules / pack.name)
        (self.root / "config" / "omega-serve.json").write_text(json.dumps({
            "server": {"engine": "native", "port": self.port, "workers": 2},
            "options": {"waf": {"enabled": True, "mode": "block", "rules": {"paths": [f"secure/waf/rules/{pack.name}"]},
                                "rate_limit": {"enabled": True, "path_policies": [
                                    {"prefix": "/limite", "requests": 3, "window_seconds": 60}]}}}}))
        (self.root / "bin").mkdir()
        (self.root / "bin" / "omega-http-core").symlink_to(BINARY)
        self._serve()
        state = self._state()
        self.assertEqual(state["effective"], "native")
        expected = max_workers("native", cpu_info().usable_cores)
        self.assertEqual(len(state["extra"]["security_pid"].split(",")), expected)
        if expected == 1:
            self.assertIn("au maximum sur cette machine", (self.root / "var" / "log" / "error.log").read_text())

        statuses = []
        for i in range(8):  # connexions distinctes : reparties sur les fils, donc sur les deux processus
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            conn.request("GET", f"/limite?n={i}")
            response = conn.getresponse()
            response.read()
            statuses.append(response.status)
            conn.close()
        self.assertEqual(statuses.count(429), 5, statuses)
        self.assertEqual(len([s for s in statuses if s != 429]), 3, statuses)

    def _serve_waf(self, extra_waf: dict | None = None, extra_server: dict | None = None,
                   security: dict | None = None) -> int:
        """WAF avec les packs body-sqli et scanner-ua ; rend le pid du processus de securite."""
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        names = ("body-sqli.json", "scanner-ua.json")
        for name in names:
            shutil.copy(REPO / "secure" / "waf" / "rules" / name, rules / name)
        waf = {"enabled": True, "mode": "block", "rules": {"paths": [f"secure/waf/rules/{n}" for n in names]},
               **(extra_waf or {})}
        config: dict = {"server": {"engine": "native", "port": self.port, **(extra_server or {})}, "options": {"waf": waf}}
        if security is not None:
            config["security"] = security
        (self.root / "config" / "omega-serve.json").write_text(json.dumps(config))
        (self.root / "bin").mkdir()
        (self.root / "bin" / "omega-http-core").symlink_to(BINARY)
        self._serve()
        state = self._state()
        self.assertEqual(state["effective"], "native")
        return int(state["extra"]["security_pid"])

    def _status(self, target: str, user_agent: str = "Mozilla/5.0", timeout: float = 5) -> int:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request("GET", target, headers={"User-Agent": user_agent})
            response = conn.getresponse()
            response.read()
            return response.status
        finally:
            conn.close()

    def test_clean_request_served_natively_attack_still_judged_by_python(self):
        # Plan WAF natif, lot 2 : processus de securite SUSPENDU -> une requete propre est servie quand meme (le
        # natif l'a reconnue seul) ; une attaque attend Python, puis est bloquee et journalisee par lui.
        security_pid = self._serve_waf()
        os.kill(security_pid, signal.SIGSTOP)
        try:
            self.assertEqual(self._status("/?q=bonjour", timeout=3), 200)
            self.assertEqual(self._status("/", user_agent="curl/8.10", timeout=3), 200)
            with self.assertRaises(TimeoutError):
                self._status("/?id=1%20union%20select%20password", timeout=1.5)
            with self.assertRaises(TimeoutError):
                self._status("/", user_agent="sqlmap/1.8", timeout=1.5)
            with self.assertRaises(TimeoutError):  # texte non ASCII : doute -> Python
                self._status("/?q=%C3%A9t%C3%A9", timeout=1.5)
        finally:
            os.kill(security_pid, signal.SIGCONT)
        self.assertEqual(self._status("/?id=1%20union%20select%20password"), 403)
        self.assertEqual(self._status("/", user_agent="sqlmap/1.8"), 403)
        self.assertEqual(self._status("/?q=%C3%A9t%C3%A9"), 200)
        alerts = (self.root / "var" / "log" / "waf-alerts.log").read_text()
        self.assertIn("SQLI-", alerts)
        self.assertIn("UA-001", alerts)
        self.assertNotIn("bonjour", alerts)

    def test_watched_sources_keep_their_decoy(self):
        # Plan WAF natif, lot 3 : leurres actifs. Une source qui recoit un leurre (affecte par le processus de
        # securite, ou ecrit en base par RIPOSTE) est envoyee a Python pour TOUTES ses requetes ; les autres sources
        # restent servies par le natif seul.
        from datetime import datetime, timedelta, timezone

        from omega_serv.domain.security.active_defense.entities import DeceptionAssignment
        from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
            open_active_defense_connection,
        )
        from omega_serv.infrastructure.persistence.sqlite_deception_assignment_repository import (
            SqliteDeceptionAssignmentRepository,
        )

        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / "secure" / "waf" / "rules" / "body-sqli.json", rules / "body-sqli.json")
        (self.root / "config" / "omega-serve.json").write_text(json.dumps({
            "server": {"engine": "native", "port": self.port},
            "options": {
                "waf": {"enabled": True, "mode": "block", "rules": {"paths": ["secure/waf/rules/body-sqli.json"]}},
                "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1"], "header_preference": ["X-Forwarded-For"]},
                "active_defense": {"enabled": True, "mode": "enforce",
                                   "war_mode": {"enabled": True, "thresholds": {"suspicious_score": 1, "hostile_score": 10,
                                                                                "incident_score": 1000}},
                                   "deception": {"enabled": True, "fallback": "pass_through", "profiles": {
                                       "fake_admin": {"enabled": True, "match_attack_classes": ["sqli"]}}}}}}))
        (self.root / "bin").mkdir()
        (self.root / "bin" / "omega-http-core").symlink_to(BINARY)
        self._serve()
        state = self._state()
        self.assertEqual(state["effective"], "native")
        security_pid = int(state["extra"]["security_pid"])

        def get(target: str, ip: str, timeout: float = 5) -> tuple[int, bytes]:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
            try:
                conn.request("GET", target, headers={"X-Forwarded-For": ip, "User-Agent": "Mozilla/5.0"})
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()

        self.assertEqual(get("/?q=1%20union%20select%20pwd%20from%20users", "203.0.113.50")[0], 403)
        status, body = get("/dashboard", "203.0.113.50")  # requete propre, mais la source a un leurre
        self.assertEqual(status, 200)
        self.assertIn(b"Connexion administrateur", body)
        self.assertEqual(get("/dashboard", "198.51.100.1")[0], 404)  # autre source : production normale

        # Leurre ecrit en base par un autre processus (comme RIPOSTE) : vu par le natif en au plus 1 s
        connection = open_active_defense_connection(self.root / "var" / "lib" / "active-defense.sqlite3")
        now = datetime.now(timezone.utc)
        SqliteDeceptionAssignmentRepository(connection).save(DeceptionAssignment(
            subject_id="198.51.100.77:x", profile_name="fake_admin", assigned_at=now, expires_at=now + timedelta(hours=1)))
        connection.close()
        time.sleep(2.0)

        os.kill(security_pid, signal.SIGSTOP)
        try:
            self.assertEqual(get("/", "198.51.100.1", timeout=3)[0], 200)  # non suivie : natif seul
            for watched in ("203.0.113.50", "198.51.100.77"):
                with self.assertRaises(TimeoutError, msg=watched):
                    get("/", watched, timeout=1.5)
        finally:
            os.kill(security_pid, signal.SIGCONT)

    def test_check_every_sends_clean_requests_to_python_too(self):
        # Plan WAF natif, lot 4 : native_check_every = 1 -> chaque requete jugee propre part quand meme a Python
        # (processus suspendu : elle attend), traitee normalement, sans desaccord journalise ; regles livrees toutes
        # gardees par le natif (aucune ligne « evaluee par Python seulement »).
        security_pid = self._serve_waf({"native_check_every": 1})
        os.kill(security_pid, signal.SIGSTOP)
        try:
            with self.assertRaises(TimeoutError):
                self._status("/?q=bonjour", timeout=1.5)
        finally:
            os.kill(security_pid, signal.SIGCONT)
        self.assertEqual(self._status("/?q=bonjour"), 200)
        errors = (self.root / "var" / "log" / "error.log").read_text() if (self.root / "var" / "log" / "error.log").exists() else ""
        self.assertNotIn("desaccord", errors)
        self.assertNotIn("evaluee par Python seulement", errors)

    def test_rule_only_python_can_evaluate_is_reported_and_respected(self):
        # Lot 4 : regle non traduisible (repetition au-dela de la limite de PCRE2) -> une ligne dans error.log ; les
        # requetes qui ont un texte dans son scope (query) vont a Python, les autres restent au natif.
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "local.json").write_text(json.dumps({"version": 1, "pack": "local", "enabled": True, "rules": [
            {"id": "LOCAL-1", "description": "long", "scope": ["query"], "pattern": "x{70000}", "weight": 10}]}))
        security_pid = self._serve_waf({"rules": {"paths": ["secure/waf/rules/body-sqli.json",
                                                            "secure/waf/rules/local.json"]}})
        errors = (self.root / "var" / "log" / "error.log").read_text()
        self.assertIn("filtre WAF natif : regle evaluee par Python seulement - LOCAL-1 : non traduite", errors)
        os.kill(security_pid, signal.SIGSTOP)
        try:
            self.assertEqual(self._status("/", timeout=3), 200)  # pas de query : natif seul
            with self.assertRaises(TimeoutError):
                self._status("/?q=bonjour", timeout=1.5)
        finally:
            os.kill(security_pid, signal.SIGCONT)
        self.assertEqual(self._status("/?q=bonjour"), 200)

    def test_rate_limit_counted_by_native_rejected_by_python(self):
        # Lot 6 : le natif compte chaque requete ; tant que la limite n'est pas atteinte, une requete propre est
        # servie sans Python (processus de securite SUSPENDU). Au-dela, elle part a Python, qui repond 429 avec
        # Retry-After et journalise comme toujours.
        security_pid = self._serve_waf({"rate_limit": {"enabled": True, "global": {"requests": 3, "window_seconds": 60}}})
        os.kill(security_pid, signal.SIGSTOP)
        try:
            for _ in range(3):
                self.assertEqual(self._status("/?q=bonjour", timeout=3), 200)
            with self.assertRaises(TimeoutError):  # 4e : limite atteinte -> Python
                self._status("/?q=bonjour", timeout=1.5)
        finally:
            os.kill(security_pid, signal.SIGCONT)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/?q=bonjour")
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 429)
            self.assertGreaterEqual(int(response.getheader("Retry-After")), 1)
        finally:
            conn.close()
        alerts = self.root / "var" / "log" / "waf-alerts.log"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and '"stage": "rate_limit"' not in (
                alerts.read_text(encoding="utf-8") if alerts.exists() else ""):
            time.sleep(0.1)
        self.assertIn('"stage": "rate_limit"', alerts.read_text(encoding="utf-8"))

    # ------------------------------------------------ correctif de securite 2.6.2 (D29, D20)
    @staticmethod
    def _cpu_seconds(pid: int) -> float:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")  # utime + stime

    @staticmethod
    def _read_all(sock: socket.socket, timeout: float = 5) -> bytes:
        sock.settimeout(timeout)
        data = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                return data
            data += chunk

    def test_half_closed_client_waiting_for_verdict_does_not_spin(self):
        # D29 : socket du client surveillee en lecture pendant l'attente du verdict (declenchement par niveau) ->
        # un client qui ferme son cote ecriture faisait tourner le fil a 100 % (99 % mesure le 2026-11-12).
        security_pid = self._serve_waf()
        native_pid = int(self._state()["native_pid"])
        os.kill(security_pid, signal.SIGSTOP)  # verdict lent (mode guerre, magnet)
        client = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        try:
            client.sendall(b"GET /?id=1%20union%20select%20password HTTP/1.1\r\nHost: localhost\r\n\r\n")
            client.shutdown(socket.SHUT_WR)
            time.sleep(0.3)
            before = self._cpu_seconds(native_pid)
            time.sleep(2)
            spent = self._cpu_seconds(native_pid) - before
        finally:
            os.kill(security_pid, signal.SIGCONT)
        try:
            self.assertLess(spent, 0.1, f"moteur natif occupe pendant l'attente du verdict : {spent:.2f} s de CPU sur 2 s")
            self.assertTrue(self._read_all(client).startswith(b"HTTP/1.1 403 "))  # verdict rendu apres la reprise
        finally:
            client.close()

    def test_client_reset_while_waiting_for_verdict_frees_the_connection(self):
        # D29 : client parti (RST) pendant l'attente : connexion liberee tout de suite, verdict tardif ignore.
        security_pid = self._serve_waf()
        os.kill(security_pid, signal.SIGSTOP)
        try:
            client = socket.create_connection(("127.0.0.1", self.port), timeout=5)
            client.sendall(b"GET /?id=1%20union%20select%20password HTTP/1.1\r\nHost: localhost\r\n\r\n")
            time.sleep(0.3)
            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, (1).to_bytes(4, "little") + (0).to_bytes(4, "little"))
            client.close()  # SO_LINGER 0 : RST
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and self._state()["connections"] != 0:
                time.sleep(0.2)
            self.assertEqual(self._state()["connections"], 0)
        finally:
            os.kill(security_pid, signal.SIGCONT)
        self.assertEqual(self._status("/?id=1%20union%20select%20password"), 403)  # rien de casse ensuite

    def _post(self, body: bytes) -> int:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            conn.request("POST", "/index.html", body=body,
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            response = conn.getresponse()
            response.read()
            return response.status
        finally:
            conn.close()

    def test_large_inspected_body_is_never_served_without_control(self):
        # D20 : body_max_inspect_bytes au-dela de la trame INSPECT (1 Mio) -> trame refusee puis fail-open : le corps
        # d'attaque de 1,5 Mo etait servi sans WAF (essai 2026-11-12). Desormais la part envoyee est plafonnee.
        self._serve_waf({"inspect": {"body_max_inspect_bytes": 2_000_000}},
                        security={"allowed_methods": ["GET", "HEAD", "POST"]})
        attack = b"id=1 union select password from users "
        self.assertEqual(self._post(attack), 403)
        self.assertEqual(self._post(attack + b"x" * 1_500_000), 403)
        errors = (self.root / "var" / "log" / "error.log").read_text()
        self.assertNotIn("servie sans controle (fail-open)", errors)
        self.assertIn("corps inspecte limite", errors)  # avertissement au demarrage

    def test_inspect_frame_too_large_is_refused_even_in_fail_open(self):
        # D20 : une tete demesuree (max_header_size tres grand) depasse la trame a elle seule : 503, jamais servie.
        self._serve_waf(extra_server={"max_header_size": 4 * 1024 * 1024})
        filler = "".join(f"X-Filler-{i}: {'a' * 30_000}\r\n" for i in range(40))  # environ 1,2 Mo de tete
        client = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            client.sendall(f"GET /?id=1%20union%20select%20password HTTP/1.1\r\nHost: localhost\r\n{filler}"
                           "Connection: close\r\n\r\n".encode())
            self.assertTrue(self._read_all(client, 10).startswith(b"HTTP/1.1 503 "))
        finally:
            client.close()
        errors = (self.root / "var" / "log" / "error.log").read_text()
        self.assertIn("trop grande pour le canal", errors)
        self.assertNotIn("servie sans controle (fail-open)", errors)

if __name__ == "__main__":
    unittest.main()
