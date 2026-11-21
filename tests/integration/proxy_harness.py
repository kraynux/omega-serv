# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Banc commun des tests du reverse proxy (plan proxy natif v2, lot 0, etape 0.1).

- `ScriptedBackend` : faux backend HTTP/1.1, reponses fixees octet par octet selon le chemin, garde les requetes
  recues (tete brute) et compte les acces par chemin.
- `ProxyProject` : projet temporaire (src/ COPIE : le serveur ecrit dans le var/ du projet dont il est lance,
  jamais dans le vrai depot), configuration avec zone reverse proxy et options de securite, puis `omega-serv serve`
  reel avec le moteur Python ou le moteur natif (binaire build-release, sous son vrai superviseur).

Chaque requete d'un test porte sa propre adresse cliente (X-Forwarded-For, relais de confiance 127.0.0.1) : aucun
compteur (limite de debit, recidive) ne passe d'un cas a l'autre."""
from __future__ import annotations

import base64
import itertools
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NATIVE_BINARY = REPO / "native" / "omega-http-core" / "build-release" / "omega-http-core"
BANNED_IP = "203.0.113.66"
USER, PASSWORD = "bob", "secret-de-test"

class Streamed:
    """Plan proxy natif v2, lot 5 : reponse ecrite par la fonction elle-meme sur la socket (en plusieurs fois, avec
    des pauses). `fn(conn, head)` rend True pour garder la connexion (requete suivante), False pour la fermer."""

    def __init__(self, fn: Callable[[socket.socket, bytes], bool]) -> None:
        self.fn = fn


# Reponses du faux backend, par chemin (sans la chaine de requete). Une valeur appelable recoit la tete brute.
Script = bytes | Callable[[bytes], bytes] | Streamed


def _echo(head: bytes) -> bytes:
    body = head
    return b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


DEFAULT_SCRIPTS: dict[str, Script] = {
    "/api/ok": b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 9\r\n\r\nreponse-b",
    "/api/echo": _echo,
    "/api/head": b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 50\r\n\r\n",  # reponse a un HEAD
    "/api/204": b"HTTP/1.1 204 No Content\r\n\r\n",
    "/api/304": b"HTTP/1.1 304 Not Modified\r\nETag: \"v1\"\r\n\r\n",
    "/api/chunked": (b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n"
                     b"5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n"),
    "/api/close": b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nfin-par-fermeture",
    "/api/cookies": (b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nSet-Cookie: a=1; Path=/\r\n"
                     b"Set-Cookie: b=2; Path=/\r\nContent-Length: 2\r\n\r\nok"),
    "/api/lowercase": b"HTTP/1.1 200 OK\r\ncontent-type: text/plain\r\ncontent-length: 2\r\n\r\nok",
    "/api/401": (b"HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm=\"b\"\r\nContent-Type: text/plain\r\n"
                 b"Content-Length: 6\r\n\r\nrefuse"),
    "/api/404": b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: 7\r\n\r\nabsente",
    "/api/slow": b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 4\r\n\r\nlent",
}
SLOW_PATHS = {"/api/slow": 3.0}  # pause avant la reponse (secondes)


class ScriptedBackend:
    def __init__(self, scripts: dict[str, Script] | None = None, port: int = 0, drop_reused: bool = False,
                 tls: ssl.SSLContext | None = None) -> None:
        """`drop_reused` (lot 5, C8) : une requete arrivee sur une connexion deja servie est lue puis la connexion
        fermee sans reponse - la connexion du pool morte au moment de l'envoi. `tls` (lot 8) : backend HTTPS ; chaque
        poignee de main reussie est notee dans `tls_sessions` (SNI recu, version, suites communes aux deux bouts),
        chaque echec compte dans `tls_failures`."""
        self.scripts = dict(DEFAULT_SCRIPTS, **(scripts or {}))
        self.drop_reused = drop_reused
        self.tls = tls
        self.tls_sessions: list[dict] = []
        self.tls_failures = 0
        if tls is not None:
            tls.sni_callback = self._note_sni
        self.connections = 0  # connexions acceptees (lot 5 : pool)
        self.dropped = 0
        self.received: list[bytes] = []
        self.hits: dict[str, int] = {}
        self._lock = threading.Lock()
        self._listener = socket.create_server(("127.0.0.1", port))
        self.port = self._listener.getsockname()[1]
        self._stopping = False
        threading.Thread(target=self._accept, daemon=True).start()

    def hits_for(self, path: str) -> int:
        with self._lock:
            return self.hits.get(path, 0)

    def requests_for(self, path: str) -> list[bytes]:
        with self._lock:
            return [head for head in self.received if head.split(b" ", 2)[1].split(b"?")[0] == path.encode()]

    def stop(self) -> None:
        self._stopping = True
        try:  # reveille le fil bloque dans accept() : sans cela le noyau garde le port (passage suivant refuse)
            self._listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._listener.close()

    def _accept(self) -> None:
        while not self._stopping:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            with self._lock:
                self.connections += 1
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    @staticmethod
    def _note_sni(ssl_socket, name, _context):  # type: ignore[no-untyped-def]
        ssl_socket.omega_sni = name

    def _serve(self, conn: socket.socket) -> None:
        if self.tls is not None:
            try:
                conn.settimeout(10)
                conn = self.tls.wrap_socket(conn, server_side=True)
                conn.settimeout(None)
            except (ssl.SSLError, OSError):
                with self._lock:
                    self.tls_failures += 1
                conn.close()
                return
            with self._lock:
                self.tls_sessions.append({"sni": getattr(conn, "omega_sni", None), "version": conn.version(),
                                          "ciphers": sorted(c[0] for c in conn.shared_ciphers() or [])})
        buffer = b""
        served = 0
        with conn:
            while True:
                while b"\r\n\r\n" not in buffer:
                    try:
                        data = conn.recv(65536)
                    except OSError:
                        return
                    if not data:
                        return
                    buffer += data
                head, buffer = buffer.split(b"\r\n\r\n", 1)
                head += b"\r\n\r\n"
                length = 0
                for line in head.split(b"\r\n")[1:]:
                    name, _, value = line.partition(b":")
                    if name.strip().lower() == b"content-length":
                        length = int(value.strip() or 0)
                while len(buffer) < length:
                    data = conn.recv(65536)
                    if not data:
                        return
                    buffer += data
                buffer = buffer[length:]
                if self.drop_reused and served > 0:
                    with self._lock:
                        self.dropped += 1
                    return
                served += 1
                method, target = head.split(b" ", 2)[:2]
                path = target.split(b"?")[0].decode("latin-1")
                with self._lock:
                    self.received.append(head)
                    self.hits[path] = self.hits.get(path, 0) + 1
                time.sleep(SLOW_PATHS.get(path, 0))
                script = self.scripts.get(path, DEFAULT_SCRIPTS["/api/ok"])
                if isinstance(script, Streamed):
                    try:
                        if not script.fn(conn, head):
                            return
                    except OSError:
                        return
                    continue
                response = script(head) if callable(script) else script
                if method == b"HEAD" and path != "/api/head":
                    response = response.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
                try:
                    conn.sendall(response)
                except OSError:
                    return
                if b"Connection: close" in response:
                    return


def basic(user: str = USER, password: str = PASSWORD) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


class ProxyProject:
    """Projet temporaire et serveur reel. `engine` : "python" ou "native"."""

    def __init__(self, engine: str, backend_port: int, options: dict | None = None,
                 server: dict | None = None, zone: dict | None = None, proxy: dict | None = None,
                 env: dict[str, str] | None = None, client_tls: bool = False) -> None:
        """`proxy` : reglages de options.reverse_proxy (plan proxy natif v2, lot 4 : {"engine": "native"} active le
        relais natif, en apercu). `env` (lot 8) : variables ajoutees a l'environnement du serveur (SSL_CERT_FILE).
        `client_tls` (lot 9) : TLS direct (certificat auto-signe genere ici) ; `exchange` et `connect` parlent HTTPS."""
        self.engine = engine
        self.extra_env = env or {}
        self.client_tls = client_tls
        self._tmp = tempfile.TemporaryDirectory(prefix="omega-proxy-")
        self.root = Path(self._tmp.name)
        shutil.copytree(REPO / "src", self.root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.bak"))
        for folder in ("webroot", "var/log", "var/run", "config"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "webroot" / "index.html").write_text("site local")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self._addresses = (f"198.51.{i // 250}.{i % 250 + 1}" for i in itertools.count())
        zone_config = {"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": backend_port}],
                       "connect_timeout_seconds": 2, "read_timeout_seconds": 1, **(zone or {})}
        config = {
            "server": {"engine": engine, "port": self.port, "bind": "127.0.0.1", "read_timeout_seconds": 5,
                       **(server or {})},
            "security": {"allowed_methods": ["GET", "HEAD", "POST"]},
            "options": {
                "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"],
                                  "header_preference": ["X-Forwarded-For"]},
                "reverse_proxy": {"enabled": True, "zones": [zone_config], **(proxy or {})},
                **(options or {}),
            },
        }
        if client_tls:
            certs = self.root / "certs"
            certs.mkdir()
            subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                            "-nodes", "-keyout", str(certs / "key.pem"), "-out", str(certs / "cert.pem"), "-days",
                            "2", "-subj", "/CN=localhost"], check=True, capture_output=True)
            config["tls"] = {"enabled": True, "mode": "direct", "certificate": {
                "certificate_path": "certs/cert.pem", "private_key_path": "certs/key.pem"}}
        self._prepare_security_files(config["options"])
        (self.root / "config" / "omega-serve.json").write_text(json.dumps(config, indent=2))
        if engine == "native":
            (self.root / "bin").mkdir()
            (self.root / "bin" / "omega-http-core").symlink_to(NATIVE_BINARY)
        self.process: subprocess.Popen[bytes] | None = None

    def _prepare_security_files(self, options: dict) -> None:
        if "waf" in options:
            rules = self.root / "secure" / "waf" / "rules"
            rules.mkdir(parents=True)
            for name in ("body-sqli.json", "scanner-ua.json"):
                shutil.copy(REPO / "secure" / "waf" / "rules" / name, rules / name)
            options["waf"].setdefault("rules", {"paths": ["secure/waf/rules/body-sqli.json",
                                                          "secure/waf/rules/scanner-ua.json"]})
            state = self.root / "var" / "lib" / "waf"
            state.mkdir(parents=True)
            (state / "blocklist.json").write_text(json.dumps({"version": 1, "entries": [{
                "network": f"{BANNED_IP}/32", "reason": "banc proxy", "created_at": "2026-11-12T00:00:00+00:00",
                "expires_at": None, "source": "manual"}]}))
        if "auth" in options:
            auth = self.root / "secure" / "auth"
            auth.mkdir(parents=True)
            sys.path.insert(0, str(REPO / "src"))
            from omega_serv.domain.security.auth.password_hashing import hash_password
            (auth / "users.json").write_text(json.dumps(
                {"version": 1, "users": [{"username": USER, "password_hash": hash_password(PASSWORD)}]}))
            (auth / "zones.json").write_text(json.dumps(
                {"version": 1, "zones": [{"path_prefix": "/api/prive", "realm": "Prive", "allowed_users": [USER]}]}))

    # ------------------------------------------------------------------ serveur
    def start(self) -> None:
        inherited = os.environ.get("PYTHONPATH", "")
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in (str(self.root / "src"), inherited) if p),
               **self.extra_env}
        self.process = subprocess.Popen(
            [sys.executable, "-m", "omega_serv", "--config", "config/omega-serve.json", "serve"],
            cwd=self.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("serveur arrete : " + self.process.stdout.read().decode(errors="replace")[-2000:])
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        time.sleep(0.5)

    def effective_engine(self) -> str:
        state = self.root / "var" / "run" / "engine-state.json"
        return json.loads(state.read_text()).get("effective", "python") if state.exists() else "python"

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(5)
        self._tmp.cleanup()

    # ------------------------------------------------------------------ requetes et journaux
    def next_address(self) -> str:
        return next(self._addresses)

    def connect(self, timeout: float = 5) -> socket.socket:
        """Connexion au serveur, chiffree en TLS direct (lot 9 : certificat de test, jamais verifie)."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        if not self.client_tls:
            return sock
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context.wrap_socket(sock, server_hostname="localhost")

    def exchange(self, raw: bytes, timeout: float = 5, close_after: float | None = None) -> bytes:
        """Envoie des octets bruts et lit jusqu'a la fermeture. `close_after` : abandon du client apres ce delai."""
        with self.connect(timeout) as sock:
            sock.sendall(raw)
            if close_after is not None:
                time.sleep(close_after)
                return b""
            chunks = []
            while True:
                try:
                    data = sock.recv(65536)
                except (TimeoutError, ConnectionResetError, ssl.SSLError):  # TLS : fin sans close_notify
                    break
                if not data:
                    break
                chunks.append(data)
        return b"".join(chunks)

    def request(self, method: str, target: str, headers: list[str] | None = None, body: bytes = b"",
                address: str | None = None, timeout: float = 5,
                forwarded: bool | None = None) -> tuple[int, dict[str, list[str]], bytes, bytes]:
        """(statut, en-tetes par nom en minuscules, corps, reponse brute). Connection: close.
        `forwarded` : en-tete X-Forwarded-For (adresse cliente simulee). Par defaut, absent sur les routes internes
        `/.omega-serv-admin/` et `/.omega-serv-load/`, comme pour la TUI et la sonde d'une instance frontale (scan de
        securite n° 1 : un appel relaye y est refuse)."""
        if forwarded is None:
            forwarded = not target.startswith(("/.omega-serv-admin/", "/.omega-serv-load/"))
        lines = [f"{method} {target} HTTP/1.1", f"Host: 127.0.0.1:{self.port}",
                 *([f"X-Forwarded-For: {address or self.next_address()}"] if forwarded else []),
                 "Connection: close", *(headers or [])]
        if body:
            lines.append(f"Content-Length: {len(body)}")
        raw = self.exchange(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body, timeout=timeout)
        return (*parse_response(raw), raw)

    def log_offsets(self) -> dict[str, int]:
        return {name: self._log(name).stat().st_size if self._log(name).exists() else 0
                for name in ("access", "waf-alerts", "error")}

    def new_lines(self, name: str, offsets: dict[str, int], wait: float = 0.4) -> list[str]:
        time.sleep(wait)  # journal ecrit apres la reponse
        path = self._log(name)
        if not path.exists():
            return []
        with path.open("rb") as handle:
            handle.seek(offsets[name])
            return [line.decode("utf-8", errors="replace") for line in handle.read().splitlines() if line]

    def _log(self, name: str) -> Path:
        return self.root / "var" / "log" / {"access": "access.log", "waf-alerts": "waf-alerts.log",
                                             "error": "error.log"}[name]


def parse_response(raw: bytes) -> tuple[int, dict[str, list[str]], bytes]:
    if b"\r\n\r\n" not in raw:
        return 0, {}, raw
    head, body = raw.split(b"\r\n\r\n", 1)
    lines = head.decode("latin-1").split("\r\n")
    try:
        status = int(lines[0].split(" ", 2)[1])
    except (IndexError, ValueError):
        return 0, {}, raw
    headers: dict[str, list[str]] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers.setdefault(name.strip().lower(), []).append(value.strip())
    return status, headers, body
