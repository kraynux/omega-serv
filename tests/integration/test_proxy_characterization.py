# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests de caracterisation du reverse proxy (plan proxy natif v2, lot 0, etape 0.2).

Comportement VOULU, dans les deux moteurs : `omega-serv serve` reel (moteur Python, puis moteur natif sous son
superviseur) devant le faux backend scripte de `proxy_harness`. Aujourd'hui le natif confie les routes proxy a
Python ; ces memes tests garderont le proxy natif des lots 4 a 6.

Un defaut connu est marque `expectedFailure` avec son numero (plan, §4) et le lot qui le corrige : le jour ou il
passe, unittest le signale (« unexpected success ») et la marque doit etre retiree."""
from __future__ import annotations

import time
import unittest
from typing import ClassVar

from tests.integration.proxy_harness import (
    BANNED_IP,
    NATIVE_BINARY,
    ProxyProject,
    ScriptedBackend,
    basic,
)

ATTACK = "/api/ok?id=1%20union%20select%20password%20from%20users"
SECURITY_OPTIONS = {
    "waf": {"enabled": True, "mode": "block",
            "rate_limit": {"enabled": True, "global": {"requests": 1000, "window_seconds": 60},
                           "path_policies": [{"prefix": "/api/limite", "requests": 3, "window_seconds": 60}]}},
    "auth": {"enabled": True},
    "access_control": {"enabled": True, "list": [{"path_prefix": "/api/interdit", "verdict": "deny"}]},
}


def _dechunk(body: bytes) -> bytes:
    out, rest = b"", body
    while rest:
        size_line, _, rest = rest.partition(b"\r\n")
        size = int(size_line.split(b";")[0], 16)
        if size == 0:
            return out
        out, rest = out + rest[:size], rest[size + 2:]
    return out


class _ProxyCharacterization:
    """Les tests ; les sous-classes fixent ENGINE. `self.project` et `self.backend` : un serveur par classe."""

    ENGINE = "python"
    PROXY: ClassVar[dict] = {}
    """options.reverse_proxy en plus (lot 4 : {"engine": "native"} = relais natif)."""
    project: ProxyProject
    backend: ScriptedBackend

    @classmethod
    def setUpClass(cls):
        cls.backend = ScriptedBackend()
        cls.project = ProxyProject(cls.ENGINE, cls.backend.port, options=SECURITY_OPTIONS, proxy=cls.PROXY)
        cls.project.start()
        if cls.project.effective_engine() != cls.ENGINE:
            cls.project.stop()
            cls.backend.stop()
            raise RuntimeError(f"moteur effectif {cls.project.effective_engine()!r}, attendu {cls.ENGINE!r}")

    @classmethod
    def tearDownClass(cls):
        cls.project.stop()
        cls.backend.stop()

    def get(self, target: str, headers: list[str] | None = None, address: str | None = None, method: str = "GET"):
        return self.project.request(method, target, headers, address=address)

    # ------------------------------------------------------------------ securite sur une route proxifiee (D16)
    def test_waf_blocks_attack_before_backend_and_writes_alert(self):
        before = self.backend.hits_for("/api/ok")
        offsets = self.project.log_offsets()
        status, _headers, _body, _raw = self.get(ATTACK)
        self.assertEqual(status, 403)
        self.assertEqual(self.backend.hits_for("/api/ok"), before)
        self.assertTrue(self.project.new_lines("waf-alerts", offsets), "aucune ligne waf-alerts")

    def test_blocklisted_address_refused_451_before_backend(self):
        before = self.backend.hits_for("/api/ok")
        status, *_ = self.get("/api/ok", address=BANNED_IP)
        self.assertEqual(status, 451)
        self.assertEqual(self.backend.hits_for("/api/ok"), before)

    def test_rate_limit_429_with_retry_after(self):
        address = self.project.next_address()
        statuses = [self.get("/api/limite", address=address)[0] for _ in range(3)]
        status, headers, _body, _raw = self.get("/api/limite", address=address)
        self.assertEqual(statuses, [200, 200, 200])
        self.assertEqual(status, 429)
        self.assertGreaterEqual(int(headers["retry-after"][0]), 1)
        self.assertEqual(self.backend.hits_for("/api/limite"), 3)

    def test_auth_required_then_granted(self):
        before = self.backend.hits_for("/api/prive")
        status, headers, _body, _raw = self.get("/api/prive")
        self.assertEqual(status, 401)
        self.assertIn("www-authenticate", headers)
        self.assertEqual(self.backend.hits_for("/api/prive"), before)
        status, *_ = self.get("/api/prive", headers=[f"Authorization: {basic()}"])
        self.assertEqual(status, 200)
        self.assertEqual(self.backend.hits_for("/api/prive"), before + 1)

    def test_access_rule_denies_before_backend(self):
        status, *_ = self.get("/api/interdit")
        self.assertEqual(status, 403)
        self.assertEqual(self.backend.hits_for("/api/interdit"), 0)

    def test_backend_401_and_404_reach_the_access_log(self):
        # Jails omega-serv-auth-bruteforce (401) et omega-serv-scan (404) : y compris ceux du backend.
        offsets = self.project.log_offsets()
        self.assertEqual(self.get("/api/401")[0], 401)
        self.assertEqual(self.get("/api/404")[0], 404)
        lines = self.project.new_lines("access", offsets)
        self.assertTrue(any('"GET /api/401 HTTP/1.1" 401 ' in line for line in lines), lines)
        self.assertTrue(any('"GET /api/404 HTTP/1.1" 404 ' in line for line in lines), lines)

    # ------------------------------------------------------------------ decoupage des reponses (C5)
    def test_head_with_content_length_has_no_body(self):
        status, headers, body, _raw = self.get("/api/head", method="HEAD")
        self.assertEqual((status, body), (200, b""))
        self.assertEqual(headers.get("content-length"), ["50"])

    def test_204_has_no_body(self):
        status, _headers, body, _raw = self.get("/api/204")
        self.assertEqual((status, body), (204, b""))

    def test_304_has_no_body(self):
        status, _headers, body, _raw = self.get("/api/304")
        self.assertEqual((status, body), (304, b""))

    def test_chunked_response_relayed_intact_and_size_logged_decoded(self):
        offsets = self.project.log_offsets()
        status, headers, body, _raw = self.get("/api/chunked")
        if "chunked" in ",".join(headers.get("transfer-encoding", [])).lower():
            body = _dechunk(body)
        self.assertEqual((status, body), (200, b"hello world"))
        lines = self.project.new_lines("access", offsets)
        self.assertTrue(any('"GET /api/chunked HTTP/1.1" 200 11 ' in line for line in lines), lines)

    def test_body_delimited_by_close(self):
        status, headers, body, _raw = self.get("/api/close")
        if "chunked" in ",".join(headers.get("transfer-encoding", [])).lower():  # relais natif en flux (lot 5)
            body = _dechunk(body)
        self.assertEqual((status, body), (200, b"fin-par-fermeture"))

    def test_size_logged_is_the_body_size(self):
        # P2 : octets du corps envoyes au client (ici `Content-Length`).
        offsets = self.project.log_offsets()
        self.assertEqual(self.get("/api/ok")[0], 200)
        lines = self.project.new_lines("access", offsets)
        self.assertTrue(any('"GET /api/ok HTTP/1.1" 200 9 ' in line for line in lines), lines)

    # ------------------------------------------------------------------ en-tetes (C6)
    def test_multiple_set_cookie_are_kept(self):
        _status, headers, _body, _raw = self.get("/api/cookies")
        self.assertEqual(sorted(headers.get("set-cookie", [])), ["a=1; Path=/", "b=2; Path=/"])

    def test_lowercase_backend_headers_are_not_duplicated(self):
        status, headers, body, _raw = self.get("/api/lowercase")
        self.assertEqual((status, body), (200, b"ok"))
        self.assertEqual(headers.get("content-length"), ["2"])

    def test_client_identity_headers_are_rewritten(self):
        # 2.6.2 (D25, P11) : jamais l'identite choisie par le client, toujours l'adresse reelle.
        address = self.project.next_address()
        self.get("/api/echo", headers=["X-Real-IP: 10.0.0.1", "Forwarded: for=10.0.0.1"], address=address)
        head = self.backend.requests_for("/api/echo")[-1].decode("latin-1")
        self.assertIn(f"X-Real-IP: {address}\r\n", head)
        self.assertIn(f"X-Forwarded-For: {address}\r\n", head)
        self.assertNotIn("10.0.0.1", head)
        self.assertNotIn("Forwarded: for", head)

    def test_control_character_in_target_refused(self):
        before = self.backend.hits_for("/api/ok\x01")
        raw = self.project.exchange(f"GET /api/ok\x01 HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: "
                                    f"{self.project.next_address()}\r\nConnection: close\r\n\r\n".encode("latin-1"))
        self.assertTrue(raw.startswith(b"HTTP/1.1 400 "), raw[:60])
        self.assertEqual(self.backend.hits_for("/api/ok\x01"), before)

    def test_dot_segments_refused_before_routing(self):
        # Lot 1 (D26) : /api/../interdit restait dans la zone /api/ et la regle d'acces de /api/interdit etait
        # evaluee sur le chemin brut ; le backend, lui, le comprenait souvent comme /interdit.
        for target in ("/api/../interdit", "/api/%2e%2e/interdit", "/api/.%2E/x", "/api/x%2f..%2finterdit"):
            with self.subTest(cible=target):
                status, *_ = self.get(target)
                self.assertEqual(status, 400)
        self.assertEqual(self.backend.hits_for("/interdit") + self.backend.hits_for("/api/interdit"), 0)

    def test_proxy_hop_counter_stops_loops(self):
        before = self.backend.hits_for("/api/ok")
        status, *_ = self.get("/api/ok", headers=["X-Omega-Proxy-Hops: 5"])
        self.assertEqual(status, 502)
        self.assertEqual(self.backend.hits_for("/api/ok"), before)

    # ------------------------------------------------------------------ erreurs et abandon (C7, C10)
    def test_backend_timeout_gives_504(self):
        status, *_ = self.get("/api/slow")
        self.assertEqual(status, 504)

    def test_client_abandon_logged_499(self):
        offsets = self.project.log_offsets()
        address = self.project.next_address()
        self.project.exchange(f"GET /api/slow HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\n\r\n"
                              .encode(), close_after=0.3)
        time.sleep(4)  # le backend repond apres 3 s
        lines = [line for line in self.project.new_lines("access", offsets) if line.startswith(address)]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn('"GET /api/slow HTTP/1.1" 499 - ', lines[0])  # taille nulle : « - », format combine

    def test_quick_answer_still_reaches_a_half_closed_client(self):
        # Garde P3 : l'abandon n'est constate que si le traitement dure ; une reponse immediate part toujours.
        import socket
        address = self.project.next_address()
        with socket.create_connection(("127.0.0.1", self.project.port), timeout=5) as sock:
            sock.sendall(f"GET /api/ok HTTP/1.1\r\nHost: localhost\r\nX-Forwarded-For: {address}\r\n"
                         "Connection: close\r\n\r\n".encode())
            sock.shutdown(socket.SHUT_WR)
            data = b""
            while chunk := sock.recv(65536):
                data += chunk
        self.assertTrue(data.startswith(b"HTTP/1.1 200 "), data[:40])


class TestProxyCharacterizationPythonEngine(_ProxyCharacterization, unittest.TestCase):
    ENGINE = "python"


def _relay_counters(project: ProxyProject) -> dict[str, int]:
    """Compteurs du relais natif (HEALTH, environ 1 fois/s, puis etat du moteur toutes les 2 s)."""
    import json
    time.sleep(3.2)
    extra = json.loads((project.root / "var" / "run" / "engine-state.json").read_text()).get("extra", {})
    return {key: int(extra.get(key, "0")) for key in ("proxy_relayed", "proxy_pending_body", "proxy_inspections",
                                                       "upstream_connections", "upstream_idle")}


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestProxyCharacterizationNativeEngine(_ProxyCharacterization, unittest.TestCase):
    ENGINE = "native"
    PROXY: ClassVar[dict] = {"engine": "python"}  # zone confiee (auto jusqu'au lot 11, relayee depuis)

    def test_zone_is_handed_off_to_python(self):
        # engine = python : le relais natif n'est pas utilise - la connexion est confiee a Python.
        self.assertEqual(self.get("/api/ok")[0], 200)
        self.assertEqual(_relay_counters(self.project)["proxy_relayed"], 0)


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestProxyCharacterizationNativeRelay(_ProxyCharacterization, unittest.TestCase):
    """Plan proxy natif v2, lot 4 : zone relayee par le moteur natif (options.reverse_proxy.engine = native). Lot 5 :
    reponses chunked et delimitees par la fermeture relayees en flux (en chunked vers un client HTTP/1.1)."""
    ENGINE = "native"
    PROXY: ClassVar[dict] = {"engine": "native"}

    def test_zone_is_relayed_natively_and_budgets_return_to_zero(self):
        before = self.backend.hits_for("/api/ok")
        for _ in range(3):
            self.assertEqual(self.get("/api/ok")[0], 200)
        self.assertEqual(self.backend.hits_for("/api/ok"), before + 3)
        counters = _relay_counters(self.project)
        self.assertGreaterEqual(counters["proxy_relayed"], 3)
        # C2, S19 : chaque reservation rendue, sur tous les chemins deja parcourus par la classe (erreurs comprises) ;
        # lot 5 : seules restent les connexions inactives du pool (S14)
        self.assertEqual((counters["proxy_pending_body"], counters["proxy_inspections"]), (0, 0))
        self.assertEqual(counters["upstream_connections"], counters["upstream_idle"])


if __name__ == "__main__":
    unittest.main()
