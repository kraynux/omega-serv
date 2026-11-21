# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 9 : TLS direct pour les zones natives (C16), cote Python (les essais de bout en bout sont
dans tests/integration/test_native_proxy_tls_direct.py).

- une zone relayee par le natif se sert en TLS direct : plus de refus avec `reverse_proxy.engine = native`, plus de
  repli complet sur Python ;
- le binaire doit annoncer `proxy_tls_direct` (un binaire plus ancien relaierait l'administration TLS au mauvais
  processus de securite) ;
- regles P7 inchangees pour une zone confiee (cache, WebSocket jusqu'au lot 10) et pour `auto` (apercu, lot 11) ;
- ecran Etat : « Reverse proxy » natif quand toutes les zones le sont."""
from __future__ import annotations

import unittest

from omega_serv.application.server.engine_levels import NATIVE, UNSUPPORTED, engine_connectors
from omega_serv.application.server.engine_selection import (
    NATIVE_PROXY_GAPS,
    TLS_HANDOFF,
    ZONE_TLS_DIRECT,
    decide_engine,
    decide_proxy_zones,
    proxy_engine_problems,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.server.native_engine import required_capabilities


def _config(engine="native", zones=None, tls_direct=True, server_engine="native"):
    data = {"server": {"engine": server_engine, "bind": "127.0.0.1", "port": 8443}, "options": {
        "reverse_proxy": {"enabled": True, "engine": engine,
                          "zones": zones or [{"url_prefix": "/app/", "upstreams": [{"host": "10.0.0.5", "port": 80}]}]}}}
    if tls_direct:
        data["tls"] = {"enabled": True, "mode": "direct"}
    return OmegaServConfig.from_dict(data)


class TestDirectTlsNativeZone(unittest.TestCase):
    def test_gap_is_lifted(self):
        self.assertNotIn(ZONE_TLS_DIRECT, NATIVE_PROXY_GAPS)

    def test_native_zone_under_direct_tls_keeps_the_native_engine(self):
        config = _config()
        self.assertEqual([(z.engine, z.reasons) for z in decide_proxy_zones(config)], [("native", ())])
        self.assertEqual(proxy_engine_problems(config).errors, ())
        self.assertEqual(proxy_engine_problems(config).warnings, ())
        decision = decide_engine(config, None)
        self.assertEqual((decision.effective, decision.reasons), ("native", ()))

    def test_binary_must_announce_proxy_tls_direct(self):
        self.assertIn("proxy_tls_direct", required_capabilities(_config()))
        self.assertNotIn("proxy_tls_direct", required_capabilities(_config(tls_direct=False)))
        # zones confiees (engine = python ; auto jusqu'au lot 11) : aucun relais natif a demander.
        self.assertNotIn("proxy_tls_direct", required_capabilities(_config(engine="python")))
        self.assertIn("proxy_tls_direct", required_capabilities(_config(engine="auto")))  # lot 11


class TestP7Unchanged(unittest.TestCase):
    def test_confided_zone_with_engine_native_is_still_refused(self):
        zones = [{"url_prefix": "/c/", "upstreams": [{"host": "10.0.0.5", "port": 80}], "cache_enabled": True}]
        problems = proxy_engine_problems(_config(zones=zones))
        self.assertEqual(len(problems.errors), 1)
        self.assertIn("cache", problems.errors[0].text)

    def test_auto_still_starts_in_python_with_a_warning(self):
        # Lot 11 : avec auto, seule une zone confiee (cache) garde le repli P7.
        zones = [{"url_prefix": "/c/", "upstreams": [{"host": "10.0.0.5", "port": 80}], "cache_enabled": True}]
        config = _config(engine="auto", zones=zones)
        self.assertEqual(len(proxy_engine_problems(config).warnings), 1)
        self.assertEqual(decide_engine(config, None).reasons, (TLS_HANDOFF,))


class TestStatusScreen(unittest.TestCase):
    def test_reverse_proxy_row_is_native_when_every_zone_is(self):
        self.assertEqual(dict(engine_connectors(_config()))["Reverse proxy"], NATIVE)

    def test_one_confided_zone_keeps_the_fallback_label(self):
        zones = [{"url_prefix": "/a/", "upstreams": [{"host": "10.0.0.5", "port": 80}]},
                 {"url_prefix": "/c/", "upstreams": [{"host": "10.0.0.5", "port": 80}], "cache_enabled": True}]
        self.assertEqual(dict(engine_connectors(_config(zones=zones)))["Reverse proxy"], UNSUPPORTED)


if __name__ == "__main__":
    unittest.main()
