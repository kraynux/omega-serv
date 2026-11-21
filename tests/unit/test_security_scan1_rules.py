# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan de securite n° 1 du 2026-11-20 : regles corrigees, une classe par cause (A a F). Les essais sur serveur reel
(deux moteurs) sont dans tests/integration/test_security_scan1_*.py ; memes cas cote natif dans
native/omega-http-core/tests/test_security_scan1.cpp."""
import hashlib
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from omega_serv.application.server.serve_proxy import build_outgoing_headers, upstream_ssl_context
from omega_serv.domain.http.cgi_env import build_cgi_env
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.routing import proxy_zone as proxy_zone_module
from omega_serv.domain.routing.proxy_zone import (
    ProxyZone,
    UpstreamTarget,
    sticky_cookie_value_for_key,
)
from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.domain.security.auth import authorize as authorize_module
from omega_serv.domain.security.auth.entities import AuthZone, UserAccount
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.domain.security.path_policy import canonical_path
from omega_serv.domain.security.trusted_proxy import is_internal_route_caller
from omega_serv.infrastructure.proxy.sticky_cookie_key import load_or_create_sticky_cookie_key
from omega_serv.infrastructure.server.http_parser import has_dot_segment
from omega_serv.infrastructure.waf.reputation_tracker import InMemoryReputationTracker


def _request(path="/", headers=(), body=None, method="GET") -> HttpRequest:
    return HttpRequest(request_id="r", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method=method, path=path,
                       raw_path=path, query="", headers=HttpHeaders.from_pairs(list(headers)), body=body,
                       content_length=None, is_tls=False)


class TestCauseACanonicalPath(unittest.TestCase):
    def test_spellings_of_one_path_share_one_canonical_form(self):
        for raw in ("/private/doc.txt", "//private/doc.txt", "/%70rivate/doc.txt", "/%2570rivate/doc.txt",
                    "/private%2fdoc.txt", "/private%5Cdoc.txt", "/private\\doc.txt", "/./private//doc.txt"):
            with self.subTest(raw=raw):
                self.assertEqual(canonical_path(raw), "/private/doc.txt")

    def test_trailing_slash_root_and_star_kept(self):
        self.assertEqual(canonical_path("/private/"), "/private/")
        self.assertEqual(canonical_path("//"), "/")
        self.assertEqual(canonical_path("*"), "*")
        self.assertEqual(canonical_path("/a%20b"), "/a b")

    def test_unusable_paths_have_no_canonical_form(self):
        for raw in ("/%FF", "/a%00b", "/a%0ab", "/a/%2e%2e/b", "/a/../b"):
            with self.subTest(raw=raw):
                self.assertIsNone(canonical_path(raw))

    def test_request_exposes_canonical_path(self):
        self.assertEqual(_request("//x/%79").canonical_path, "/x/y")


class TestCauseBDotSegments(unittest.TestCase):
    def test_once_and_twice_encoded_dot_segments_detected(self):
        for target in ("/a/%2e%2e/b", "/a/%252e%252e/b", "/a/%252E%252E%252Fb", "/a/.%2e/b", "/a\\..\\b"):
            with self.subTest(target=target):
                self.assertTrue(has_dot_segment(target))

    def test_ordinary_targets_pass(self):
        for target in ("/a/b.txt", "/a%20b", "/a/%25252e%25252e/b", "/.well-known/x", "*"):
            with self.subTest(target=target):
                self.assertFalse(has_dot_segment(target))


class TestCauseCProxyFraming(unittest.TestCase):
    def _zone(self):
        return ProxyZone(url_prefix="/api/", upstreams=(UpstreamTarget(host="127.0.0.1", port=3000),))

    def _sent(self, request):
        zone = self._zone()
        return build_outgoing_headers(request, zone, zone.upstreams[0])

    def test_length_named_in_connection_is_recomputed(self):
        body = b"GET /smuggled HTTP/1.1\r\nHost: x\r\n\r\n"
        sent = self._sent(_request("/api/x", [("Content-Length", str(len(body))), ("Connection", "Content-Length")],
                                   body=body, method="POST"))
        lengths = [value for name, value in sent if name.lower() == "content-length"]
        self.assertEqual(lengths, [str(len(body))])

    def test_client_length_never_relayed_as_is(self):
        sent = self._sent(_request("/api/x", [("Content-Length", "999")], body=b"ok", method="POST"))
        self.assertEqual([value for name, value in sent if name.lower() == "content-length"], ["2"])

    def test_chunked_body_gets_a_length(self):
        sent = self._sent(_request("/api/x", [("Transfer-Encoding", "chunked")], body=b"abc", method="POST"))
        self.assertIn(("Content-Length", "3"), sent)
        self.assertFalse(any(name.lower() == "transfer-encoding" for name, _ in sent))

    def test_bodiless_request_gets_no_length(self):
        self.assertFalse(any(name.lower() == "content-length" for name, _ in self._sent(_request("/api/x"))))


class TestCauseDInternalRoutes(unittest.TestCase):
    def test_trusted_peer_without_relay_headers_accepted(self):
        self.assertTrue(is_internal_route_caller("127.0.0.1", ["127.0.0.1/32"], ["Host", "User-Agent"]))

    def test_relay_headers_refused_even_from_trusted_peer(self):
        for name in ("X-Forwarded-For", "forwarded", "X-REAL-IP", "CF-Connecting-IP", "X-Forwarded-Host"):
            with self.subTest(name=name):
                self.assertFalse(is_internal_route_caller("127.0.0.1", ["127.0.0.1/32"], ["Host", name]))

    def test_untrusted_peer_refused(self):
        self.assertFalse(is_internal_route_caller("203.0.113.5", ["127.0.0.1/32"], ["Host"]))


class TestCauseEDenialOfService(unittest.TestCase):
    def test_reputation_tracker_is_capped_least_recent_first(self):
        clock = mock.Mock()
        clock.now.return_value = datetime(2026, 11, 20, tzinfo=timezone.utc)
        tracker = InMemoryReputationTracker(clock, max_tracked_keys=3)
        for ip in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
            tracker.record_hit(ip)
        tracker.record_hit("10.0.0.1")  # touchee : redevient la plus recente
        tracker.record_hit("10.0.0.4")  # table pleine : 10.0.0.2 oubliee
        self.assertEqual(tracker.count_hits_in_window("10.0.0.2", 60), 0)
        self.assertEqual(tracker.count_hits_in_window("10.0.0.1", 60), 2)
        self.assertEqual(tracker.count_hits_in_window("10.0.0.4", 60), 1)
        clock.now.return_value += timedelta(seconds=1)
        self.assertLessEqual(len(tracker._hits), 3)

    def test_successful_password_check_is_remembered(self):
        authorize_module.forget_verified_credentials()
        user = UserAccount(username="bob", password_hash=hash_password("motdepasse"))
        zones = (Zone(path_prefix="/prive", data=AuthZone(path_prefix="/prive", realm="P", allowed_users=("bob",))),)
        users = {"bob": user}
        import base64
        good = "Basic " + base64.b64encode(b"bob:motdepasse").decode()
        bad = "Basic " + base64.b64encode(b"bob:faux").decode()
        self.assertTrue(authorize_module.password_check_is_costly("/prive/x", good, zones, users))
        self.assertFalse(authorize_module.password_check_is_costly("/public", good, zones, users))
        self.assertFalse(authorize_module.password_check_is_costly("/prive/x", None, zones, users))
        self.assertEqual(authorize_module.authorize_request("/prive/x", "GET", good, zones, users).outcome, "allowed")
        self.assertFalse(authorize_module.password_check_is_costly("/prive/x", good, zones, users))
        started = time.monotonic()
        self.assertEqual(authorize_module.authorize_request("/prive/x", "GET", good, zones, users).outcome, "allowed")
        self.assertLess(time.monotonic() - started, 0.05)  # sans nouveau scrypt
        self.assertEqual(authorize_module.authorize_request("/prive/x", "GET", bad, zones, users).outcome,
                         "unauthenticated")
        self.assertTrue(authorize_module.password_check_is_costly("/prive/x", bad, zones, users))
        changed = {"bob": UserAccount(username="bob", password_hash=hash_password("autre"))}
        self.assertTrue(authorize_module.password_check_is_costly("/prive/x", good, zones, changed))
        self.assertTrue(all(b"motdepasse" not in key for key in authorize_module._verified))


class TestCauseFMinor(unittest.TestCase):
    def test_upstream_tls_never_gets_a_missing_context(self):
        from omega_serv.application.server.client_tls import set_client_context_factory
        from omega_serv.application.server.start_server import _client_context
        set_client_context_factory(_client_context)  # comme au demarrage du serveur
        zone = ProxyZone(url_prefix="/leurre/", upstreams=(UpstreamTarget(host="127.0.0.1", port=3443, use_tls=True),))
        context = upstream_ssl_context(zone.upstreams[0], zone, None, None)
        self.assertIsNotNone(context)
        plain = UpstreamTarget(host="127.0.0.1", port=3000)
        self.assertIsNone(upstream_ssl_context(plain, zone, None, None))

    def test_cgi_env_drops_proxy_and_underscore_headers(self):
        request = _request("/x.php", [("Proxy", "http://attaquant:8080"), ("X_Forwarded_For", "1.2.3.4"),
                                      ("Accept", "text/html")])
        env = build_cgi_env(request, "/srv/x.php", "/x.php", "/srv", "x", 80)
        self.assertNotIn("HTTP_PROXY", env)
        self.assertNotIn("HTTP_X_FORWARDED_FOR", env)
        self.assertEqual(env["HTTP_ACCEPT"], "text/html")

    def test_sticky_cookie_keyed_with_instance_secret(self):
        previous = proxy_zone_module._sticky_cookie_key  # un autre test a pu demarrer un proxy et poser sa cle
        self.addCleanup(proxy_zone_module.set_sticky_cookie_key, previous)
        proxy_zone_module.set_sticky_cookie_key(None)
        unkeyed = hashlib.sha256(b"10.0.0.5:8080").hexdigest()[:16]
        self.assertEqual(sticky_cookie_value_for_key("10.0.0.5:8080"), unkeyed)
        with tempfile.TemporaryDirectory() as folder:
            key = load_or_create_sticky_cookie_key(Path(folder))
            self.assertIsNotNone(key)
            self.assertEqual(load_or_create_sticky_cookie_key(Path(folder)), key)  # relue, jamais remplacee
            self.assertEqual(sorted(p.name for p in (Path(folder) / "var/lib/proxy").iterdir()), ["sticky-cookie.key"])
            proxy_zone_module.set_sticky_cookie_key(key)
            try:
                keyed = sticky_cookie_value_for_key("10.0.0.5:8080")
            finally:
                proxy_zone_module.set_sticky_cookie_key(None)
        self.assertNotEqual(keyed, unkeyed)
        self.assertEqual(len(keyed), 16)

    def test_audit_line_escapes_line_breaks(self):
        from omega_serv.bootstrap.container import DependencyContainer
        written = []
        fake = mock.Mock()
        fake.logger.append_line.side_effect = lambda path, line: written.append(line)
        fake._project_root = Path("/tmp")
        DependencyContainer.admin_audit(fake, "action ok\r2026-01-01T00:00:00Z faux faux\x85faux\nfaux")
        self.assertEqual(len(written), 1)
        self.assertEqual(len(written[0].splitlines()), 1)
        self.assertIn("\\r", written[0])


if __name__ == "__main__":
    unittest.main()
