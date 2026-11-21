# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 8 : TLS vers le backend, cote Python (les essais de bout en bout sont dans
tests/integration/test_native_proxy_upstream_tls.py).

- une zone avec un backend HTTPS est relayee par le natif, qui doit alors annoncer `proxy_tls` ;
- mode non verifie : un avertissement par zone concernee (demarrage, rechargement, config check) ;
- echec TLS : une ligne au plus par backend et par minute ; lecture des exceptions du module ssl."""
from __future__ import annotations

import ssl
import unittest

from omega_serv.application.config.validate_config import (
    config_problems,
    unverified_upstream_tls_warnings,
)
from omega_serv.application.server import serve_proxy
from omega_serv.application.server.engine_selection import decide_proxy_zones
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_zone import UpstreamTarget
from omega_serv.infrastructure.proxy.asyncio_http_proxy_client import tls_failure
from omega_serv.infrastructure.server.native_engine import required_capabilities
from omega_serv.ports.http_proxy_client_port import HttpProxyTlsError


def _config(zones, engine="native"):
    return OmegaServConfig.from_dict({"server": {"engine": "native", "port": 8080, "bind": "127.0.0.1"}, "options": {
        "reverse_proxy": {"enabled": True, "engine": engine, "zones": zones}}})


def _zone(prefix="/api/", tls=True, verify=True):
    return {"url_prefix": prefix, "upstreams": [{"host": "127.0.0.1", "port": 8443, "use_tls": tls}],
            "verify_upstream_tls": verify}


class TestNativeZoneWithUpstreamTls(unittest.TestCase):
    def test_zone_with_https_backend_is_relayed_natively_and_needs_proxy_tls(self):
        config = _config([_zone()])
        self.assertEqual([z.engine for z in decide_proxy_zones(config)], ["native"])
        self.assertIn("proxy_tls", required_capabilities(config))

    def test_plain_zone_does_not_need_proxy_tls(self):
        self.assertNotIn("proxy_tls", required_capabilities(_config([_zone(tls=False)])))

    def test_zone_kept_in_python_does_not_need_proxy_tls(self):
        self.assertNotIn("proxy_tls", required_capabilities(_config([_zone()], engine="python")))


class TestUnverifiedWarning(unittest.TestCase):
    def test_one_warning_per_unverified_zone_with_an_https_backend(self):
        config = _config([_zone("/a/", verify=False), _zone("/b/", verify=True), _zone("/c/", tls=False, verify=False)])
        warnings = unverified_upstream_tls_warnings(config)
        self.assertEqual([w.log_text for w in warnings], [
            "options.reverse_proxy zone '/a/' : certificat des backends HTTPS non vérifié (verify_upstream_tls = false)"])
        self.assertIn(warnings[0], config_problems(config).warnings)  # demarrage et config check

    def test_no_warning_without_reverse_proxy(self):
        config = OmegaServConfig.from_dict({"server": {"port": 8080, "bind": "127.0.0.1"}})
        self.assertEqual(unverified_upstream_tls_warnings(config), [])


class TestTlsFailureLine(unittest.TestCase):
    def setUp(self):
        serve_proxy._tls_failure_logged_at.clear()
        self.addCleanup(serve_proxy._tls_failure_logged_at.clear)
        self.lines: list[str] = []
        self.upstream = UpstreamTarget(host="127.0.0.1", port=8443, use_tls=True)

    def test_at_most_one_line_per_backend_and_per_minute(self):
        error = HttpProxyTlsError("x", "self-signed certificate", certificate=True)
        self.assertTrue(serve_proxy.log_tls_failure(self.lines.append, self.upstream, error, now=100.0))
        self.assertFalse(serve_proxy.log_tls_failure(self.lines.append, self.upstream, error, now=159.9))
        other = UpstreamTarget(host="127.0.0.2", port=8443, use_tls=True)
        self.assertTrue(serve_proxy.log_tls_failure(self.lines.append, other, error, now=120.0))  # autre backend
        self.assertTrue(serve_proxy.log_tls_failure(self.lines.append, self.upstream, error, now=160.0))
        self.assertEqual(self.lines, [
            "reverse proxy : certificat de 127.0.0.1:8443 refusé : self-signed certificate",
            "reverse proxy : certificat de 127.0.0.2:8443 refusé : self-signed certificate",
            "reverse proxy : certificat de 127.0.0.1:8443 refusé : self-signed certificate"])

    def test_handshake_failure_text(self):
        error = HttpProxyTlsError("x", "WRONG_VERSION_NUMBER", certificate=False)
        serve_proxy.log_tls_failure(self.lines.append, self.upstream, error, now=1.0)
        self.assertEqual(self.lines, [("reverse proxy : poignée de main TLS avec 127.0.0.1:8443 impossible : "
                                       "WRONG_VERSION_NUMBER")])

    def test_ssl_exceptions_are_read_without_importing_ssl_in_the_client(self):
        certificate = ssl.SSLCertVerificationError(1, "certificate verify failed")
        certificate.verify_code = 18
        certificate.verify_message = "self-signed certificate"
        self.assertEqual(tls_failure(certificate), ("self-signed certificate", True))
        protocol = ssl.SSLError(1, "wrong version number")
        protocol.reason = "WRONG_VERSION_NUMBER"
        self.assertEqual(tls_failure(protocol), ("WRONG_VERSION_NUMBER", False))
        self.assertIsNone(tls_failure(ssl.SSLEOFError(8, "EOF")))  # backend parti : connexion impossible, sans ligne
        self.assertIsNone(tls_failure(ConnectionRefusedError()))
        self.assertIsNone(tls_failure(TimeoutError()))


if __name__ == "__main__":
    unittest.main()
