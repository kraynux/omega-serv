# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 8 : TLS vers le backend (C15, S15), de bout en bout, dans les deux moteurs.

Critere du lot : certificat auto-signe et vraie CA (CA de test, donnee par SSL_CERT_FILE comme le magasin du systeme),
pool separe selon la verification. En plus : SNI seulement pour un nom, nom ou adresse verifies, memes versions et
memes suites proposees que Python, poignee de main bornee par connect_timeout_seconds, reponse longue lue lentement.

Decisions de l'auteur (2026-11-13) :
- mode non verifie (verify_upstream_tls = false avec un backend HTTPS) : une ligne dans error.log au demarrage et a
  chaque rechargement, dans les deux moteurs ;
- certificat refuse (ou autre echec TLS) : une ligne dans error.log, au plus une par backend et par minute, dans les
  deux moteurs.

Le binaire n'est pas versionne : sans build, ces tests sont sautes."""
from __future__ import annotations

import json
import re
import signal
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests.integration.proxy_harness import NATIVE_BINARY, ProxyProject, ScriptedBackend, Streamed

ENGINES = ("python", "native")
_CERTS: tempfile.TemporaryDirectory[str] | None = None
CERTS = Path()


def _openssl(*args: str) -> None:
    subprocess.run(["openssl", *args], check=True, capture_output=True)


def setUpModule() -> None:
    """CA de test et trois certificats : signe pour 127.0.0.1 et localhost, signe pour un autre nom, auto-signe."""
    global _CERTS, CERTS
    _CERTS = tempfile.TemporaryDirectory(prefix="omega-lot8-")
    CERTS = Path(_CERTS.name)
    _openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=CA de test omega",
             "-keyout", str(CERTS / "ca.key"), "-out", str(CERTS / "ca.pem"),
             "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
             "-addext", "subjectKeyIdentifier=hash")
    for name, san in (("bon", "IP:127.0.0.1,DNS:localhost"), ("autre", "DNS:autre.test")):
        _openssl("req", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={name}",
                 "-keyout", str(CERTS / f"{name}.key"), "-out", str(CERTS / f"{name}.csr"))
        (CERTS / f"{name}.ext").write_text(
            f"subjectAltName={san}\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\nauthorityKeyIdentifier=keyid\nsubjectKeyIdentifier=hash\n")
        _openssl("x509", "-req", "-in", str(CERTS / f"{name}.csr"), "-CA", str(CERTS / "ca.pem"),
                 "-CAkey", str(CERTS / "ca.key"), "-CAcreateserial", "-days", "2",
                 "-extfile", str(CERTS / f"{name}.ext"), "-out", str(CERTS / f"{name}.pem"))
    _openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=127.0.0.1",
             "-keyout", str(CERTS / "auto.key"), "-out", str(CERTS / "auto.pem"),
             "-addext", "subjectAltName=IP:127.0.0.1")


def tearDownModule() -> None:
    if _CERTS is not None:
        _CERTS.cleanup()


def _context(name: str, ciphers: str | None = None) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(CERTS / f"{name}.pem"), str(CERTS / f"{name}.key"))
    if ciphers:
        context.set_ciphers(ciphers)
    return context


def _named(name: str) -> bytes:
    body = name.encode()
    return b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def _lines(project: ProxyProject, start: str) -> list[str]:
    """Lignes d'error.log qui commencent par `start`, sans la date ni l'identifiant de requete final."""
    return re.findall(rf"({re.escape(start)}.*?)(?: \[[0-9a-f]{{16}}\])?$", _errors(project), re.MULTILINE)


def _errors(project: ProxyProject) -> str:
    path = project.root / "var" / "log" / "error.log"
    return path.read_text() if path.exists() else ""


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestUpstreamTls(unittest.TestCase):
    def _backend(self, name: str, ciphers: str | None = None) -> ScriptedBackend:
        backend = ScriptedBackend({"/api/qui": _named(name)}, tls=_context(name, ciphers))
        self.addCleanup(backend.stop)
        return backend

    def _project(self, engine: str, port: int, *, verify: bool, host: str = "127.0.0.1", trust_ca: bool = False,
                 zones: list[dict] | None = None) -> ProxyProject:
        zone = {"upstreams": [{"host": host, "port": port, "use_tls": True}], "verify_upstream_tls": verify,
                "read_timeout_seconds": 5}
        proxy: dict = {"engine": "native"} if engine == "native" else {}
        if zones is not None:
            proxy["zones"] = zones
        project = ProxyProject(engine, port, zone=zone, proxy=proxy or None,
                               env={"SSL_CERT_FILE": str(CERTS / "ca.pem")} if trust_ca else None)
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), engine)
        return project

    # ---------------------------------------------------------------- certificat auto-signe
    def test_self_signed_backend_without_verification_is_served_and_signalled(self):
        line = ("avertissement : options.reverse_proxy zone '/api/' : certificat des backends HTTPS non vérifié "
                "(verify_upstream_tls = false)")
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend("auto")
                project = self._project(engine, backend.port, verify=False)
                status, _headers, body, _raw = project.request("GET", "/api/qui")
                self.assertEqual((status, body), (200, b"auto"))
                self.assertEqual(_errors(project).count(line), 1)  # demarrage
                assert project.process is not None
                project.process.send_signal(signal.SIGHUP)
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline and _errors(project).count(line) < 2:
                    time.sleep(0.1)
                self.assertEqual(_errors(project).count(line), 2)  # rechargement

    def test_self_signed_backend_with_verification_gives_502_and_one_line_a_minute(self):
        lines = {}
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend("auto")
                project = self._project(engine, backend.port, verify=True)
                self.assertEqual([project.request("GET", "/api/qui")[0] for _ in range(3)], [502] * 3)
                self.assertEqual(backend.hits_for("/api/qui"), 0)  # jamais une requete sur une connexion non sure
                found = _lines(project, "reverse proxy : certificat de ")
                self.assertEqual(found, [(f"reverse proxy : certificat de 127.0.0.1:{backend.port} refusé : "
                                          "self-signed certificate")])
                lines[engine] = found[0].replace(str(backend.port), "PORT")
        self.assertEqual(lines["native"], lines["python"])

    # ---------------------------------------------------------------- vraie CA
    def test_certificate_from_a_trusted_ca_is_accepted_without_sni_for_an_address(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend("bon")
                project = self._project(engine, backend.port, verify=True, trust_ca=True)
                status, _headers, body, _raw = project.request("GET", "/api/qui")
                self.assertEqual((status, body), (200, b"bon"))
                self.assertEqual(backend.tls_sessions[0]["sni"], None)  # adresse IP : pas de SNI (comme Python)
                self.assertNotIn("non vérifié", _errors(project))
                if engine == "native":
                    time.sleep(3.2)
                    extra = json.loads((project.root / "var" / "run" / "engine-state.json").read_text())["extra"]
                    self.assertGreaterEqual(int(extra["proxy_relayed"]), 1)  # relayee par le natif, pas confiee

    def test_name_is_sent_as_sni_and_verified(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend("bon")
                project = self._project(engine, backend.port, verify=True, host="localhost", trust_ca=True)
                self.assertEqual({project.request("GET", "/api/qui")[2] for _ in range(3)}, {b"bon"})
                self.assertEqual({session["sni"] for session in backend.tls_sessions}, {"localhost"})

    def test_certificate_for_another_name_is_refused(self):
        lines = {}
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend("autre")
                project = self._project(engine, backend.port, verify=True, trust_ca=True)
                self.assertEqual(project.request("GET", "/api/qui")[0], 502)
                found = _lines(project, "reverse proxy : certificat de ")
                self.assertEqual(found, [(f"reverse proxy : certificat de 127.0.0.1:{backend.port} refusé : "
                                          "IP address mismatch, certificate is not valid for '127.0.0.1'.")])
                lines[engine] = found[0].replace(str(backend.port), "PORT")
        self.assertEqual(lines["native"], lines["python"])

    def test_offered_versions_and_cipher_suites_are_python_ones(self):
        sessions = {}
        for engine in ENGINES:
            backend = self._backend("bon", ciphers="ALL:@SECLEVEL=0")  # tout accepte : on voit ce que le client offre
            project = self._project(engine, backend.port, verify=True, trust_ca=True)
            self.assertEqual(project.request("GET", "/api/qui")[0], 200)
            sessions[engine] = backend.tls_sessions[0]
        self.assertEqual(sessions["native"]["version"], sessions["python"]["version"])
        self.assertEqual(sessions["native"]["ciphers"], sessions["python"]["ciphers"])
        self.assertTrue(sessions["native"]["ciphers"])

    # ---------------------------------------------------------------- pool
    def test_pool_reuses_tls_connections_and_never_mixes_verification_policies(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = self._backend("bon")
                upstream = {"host": "127.0.0.1", "port": backend.port, "use_tls": True}
                zones = [{"url_prefix": prefix, "upstreams": [upstream], "verify_upstream_tls": verify,
                          "connect_timeout_seconds": 2, "read_timeout_seconds": 5}
                         for prefix, verify in (("/api/", True), ("/bis/", False))]
                project = self._project(engine, backend.port, verify=True, trust_ca=True, zones=zones)
                for _ in range(3):
                    self.assertEqual(project.request("GET", "/api/qui")[0], 200)
                    time.sleep(0.1)
                self.assertEqual(backend.connections, 1)  # connexion TLS gardee et reprise (tickets TLS 1.3 compris)
                self.assertEqual(project.request("GET", "/bis/qui")[0], 200)
                self.assertEqual(backend.connections, 2)  # zone non verifiee : jamais la connexion verifiee
                self.assertEqual(project.request("GET", "/api/qui")[0], 200)
                self.assertEqual(backend.connections, 2)

    # ---------------------------------------------------------------- flux
    def test_long_response_read_slowly_arrives_whole(self):
        payload = bytes(range(256)) * 16384  # 4 Mio : contre-pression du relais natif, lecture TLS reprise

        def big(conn: socket.socket, _head: bytes) -> bool:
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: "
                         + str(len(payload)).encode() + b"\r\n\r\n")
            for offset in range(0, len(payload), 65536):
                conn.sendall(payload[offset:offset + 65536])
            return True

        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = ScriptedBackend({"/api/gros": Streamed(big)}, tls=_context("bon"))
                self.addCleanup(backend.stop)
                project = self._project(engine, backend.port, verify=True, trust_ca=True)
                sock = socket.create_connection(("127.0.0.1", project.port), timeout=20)
                self.addCleanup(sock.close)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16384)
                sock.sendall(f"GET /api/gros HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {project.next_address()}"
                             "\r\nConnection: close\r\n\r\n".encode())
                received = bytearray()
                while True:
                    data = sock.recv(8192)
                    if not data:
                        break
                    received += data
                    if len(received) < 1024 * 1024:
                        time.sleep(0.002)  # client lent au debut : le relais suspend puis reprend la lecture
                head, _, body = bytes(received).partition(b"\r\n\r\n")
                self.assertTrue(head.startswith(b"HTTP/1.1 200 "), head[:40])
                self.assertEqual(body, payload)


class _SilentBackend:
    """Accepte la connexion TCP sans jamais repondre (poignee de main jamais finie), ou repond en clair (`reply`)."""

    def __init__(self, reply: bytes | None = None) -> None:
        self.reply = reply
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self._held: list[socket.socket] = []
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            if self.reply is None:
                self._held.append(conn)
                continue
            try:
                conn.recv(65536)
                conn.sendall(self.reply)
            except OSError:
                pass
            conn.close()

    def stop(self) -> None:
        for conn in self._held:
            conn.close()
        try:
            self._listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._listener.close()


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestUpstreamTlsFailures(unittest.TestCase):
    def _project(self, engine: str, port: int) -> ProxyProject:
        project = ProxyProject(engine, port, zone={"upstreams": [{"host": "127.0.0.1", "port": port, "use_tls": True}],
                                                   "connect_timeout_seconds": 1, "read_timeout_seconds": 5},
                               proxy={"engine": "native"} if engine == "native" else None)
        self.addCleanup(project.stop)
        project.start()
        self.assertEqual(project.effective_engine(), engine)
        return project

    def test_handshake_is_bounded_by_the_connect_timeout(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = _SilentBackend()
                self.addCleanup(backend.stop)
                project = self._project(engine, backend.port)
                started = time.monotonic()
                self.assertEqual(project.request("GET", "/api/qui", timeout=10)[0], 502)
                self.assertLess(time.monotonic() - started, 3.0)  # connect_timeout_seconds = 1
                self.assertNotIn("poignée de main TLS", _errors(project))  # un delai n'est pas un echec TLS

    def test_backend_answering_in_clear_gives_the_same_line_in_both_engines(self):
        lines = {}
        for engine in ENGINES:
            with self.subTest(engine=engine):
                backend = _SilentBackend(reply=b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
                self.addCleanup(backend.stop)
                project = self._project(engine, backend.port)
                self.assertEqual(project.request("GET", "/api/qui")[0], 502)
                found = _lines(project, "reverse proxy : poignée de main TLS avec ")
                self.assertEqual(len(found), 1, _errors(project))
                lines[engine] = found[0].replace(str(backend.port), "PORT")
        self.assertEqual(lines["native"], lines["python"])


if __name__ == "__main__":
    unittest.main()
