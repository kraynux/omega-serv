# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 11 : fin de l'apercu du relais natif, cote Python.

- `AUTO_PENDING` leve : avec `options.reverse_proxy.engine = auto` (defaut), chaque zone que le natif sait relayer
  est native ; seul le cache reste confie a Python (Q6) ;
- ecran Etat : detail par zone quand certaines zones seulement sont confiees ;
- TLS direct : une zone ordinaire ne fait plus demarrer en Python avec auto."""
from __future__ import annotations

import unittest

from omega_serv.application.server.engine_levels import (
    NATIVE,
    PYTHON_CONNECTION,
    UNSUPPORTED,
    engine_connectors,
    zone_engine_labels,
)
from omega_serv.application.server.engine_selection import (
    AUTO_PENDING,
    NATIVE_PROXY_GAPS,
    ZONE_CACHE,
    decide_engine,
    decide_proxy_zones,
    proxy_engine_problems,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.server.native_engine import required_capabilities


def _zone(prefix, **extra):
    return {"url_prefix": prefix, "upstreams": [{"host": "10.0.0.5", "port": 8080}], **extra}


def _config(zones, engine="auto", tls_direct=False):
    data = {"server": {"engine": "native", "bind": "127.0.0.1", "port": 8080}, "options": {
        "reverse_proxy": {"enabled": True, "engine": engine, "zones": zones}}}
    if tls_direct:
        data["tls"] = {"enabled": True, "mode": "direct"}
    return OmegaServConfig.from_dict(data)


class TestAutoIsNative(unittest.TestCase):
    def test_no_gap_left(self):
        self.assertEqual(NATIVE_PROXY_GAPS, frozenset())

    def test_auto_relays_every_feature_but_the_cache(self):
        zones = [_zone("/simple/"), _zone("/ws/", websocket_enabled=True),
                 _zone("/lb/", upstreams=[{"host": "10.0.0.5", "port": 1}, {"host": "10.0.0.6", "port": 1}],
                       sticky_session_enabled=True),
                 _zone("/tls/", upstreams=[{"host": "10.0.0.5", "port": 443, "use_tls": True}]),
                 _zone("/c/", cache_enabled=True)]
        decided = [(z.url_prefix, z.engine, z.reasons) for z in decide_proxy_zones(_config(zones))]
        self.assertEqual(decided, [("/simple/", "native", ()), ("/ws/", "native", ()), ("/lb/", "native", ()),
                                   ("/tls/", "native", ()), ("/c/", "python", (ZONE_CACHE,))])
        needed = required_capabilities(_config(zones))
        self.assertTrue({"proxy_relay", "proxy_balance", "proxy_tls", "proxy_websocket"} <= needed)

    def test_python_engine_still_delegates_everything(self):
        decided = decide_proxy_zones(_config([_zone("/a/")], engine="python"))
        self.assertEqual([z.engine for z in decided], ["python"])

    def test_direct_tls_with_ordinary_zones_keeps_the_native_engine(self):
        # Avant le lot 11 : auto confiait la zone, et TLS direct faisait tout demarrer en Python (P7).
        config = _config([_zone("/a/")], tls_direct=True)
        self.assertEqual(proxy_engine_problems(config).warnings, ())
        self.assertEqual(decide_engine(config, None).effective, "native")
        before = proxy_engine_problems(config, frozenset({AUTO_PENDING}))
        self.assertEqual(len(before.warnings), 1)


class TestConnectorsPerZone(unittest.TestCase):
    def _proxy_rows(self, config):
        rows = engine_connectors(config)
        start = next(i for i, (label, _mode) in enumerate(rows) if label == "Reverse proxy")
        return rows[start:]

    def test_all_native(self):
        self.assertEqual(self._proxy_rows(_config([_zone("/a/"), _zone("/b/")])), [("Reverse proxy", NATIVE)])

    def test_mixed_lists_each_delegated_zone(self):
        config = _config([_zone("/a/"), _zone("/cache/", cache_enabled=True), _zone("/b/")])
        self.assertEqual(self._proxy_rows(config), [("Reverse proxy", NATIVE), ("  /cache/", PYTHON_CONNECTION)])

    def test_long_prefix_is_shortened(self):
        long_prefix = "/un/prefixe/vraiment/tres/long/"
        rows = self._proxy_rows(_config([_zone("/a/"), _zone(long_prefix, cache_enabled=True)]))
        self.assertEqual(rows[1], ("  /un/prefixe/vra…", PYTHON_CONNECTION))

    def test_every_zone_delegated_keeps_one_row(self):
        self.assertEqual(self._proxy_rows(_config([_zone("/c/", cache_enabled=True)])),
                         [("Reverse proxy", PYTHON_CONNECTION)])

    def test_direct_tls_with_a_delegated_zone_is_one_unsupported_row(self):
        config = _config([_zone("/a/"), _zone("/c/", cache_enabled=True)], tls_direct=True)
        self.assertEqual(self._proxy_rows(config), [("Reverse proxy", UNSUPPORTED)])


class TestZoneEngineColumn(unittest.TestCase):
    """Retour de l'auteur du 2026-11-14 : colonne « Moteur » de l'ecran Reverse proxy, zone par zone."""

    def test_native_and_cache(self):
        config = _config([_zone("/a/"), _zone("/c/", cache_enabled=True)])
        self.assertEqual(zone_engine_labels(config), {"/a/": "natif", "/c/": "Python (cache)"})

    def test_engine_python_setting(self):
        self.assertEqual(zone_engine_labels(_config([_zone("/a/")], engine="python")), {"/a/": "Python (réglage)"})

    def test_python_server_engine(self):
        data = {"server": {"engine": "python"}, "options": {"reverse_proxy": {"enabled": True, "zones": [_zone("/a/")]}}}
        self.assertEqual(zone_engine_labels(OmegaServConfig.from_dict(data)), {"/a/": "Python"})

    def test_direct_tls_with_a_delegated_zone_falls_back_entirely(self):
        config = _config([_zone("/a/"), _zone("/c/", cache_enabled=True)], tls_direct=True)
        self.assertEqual(zone_engine_labels(config), {"/a/": "Python (repli)", "/c/": "Python (repli)"})

    def test_direct_tls_with_ordinary_zones_stays_native(self):
        self.assertEqual(zone_engine_labels(_config([_zone("/a/")], tls_direct=True)), {"/a/": "natif"})

    def test_disabled_option_has_no_label(self):
        data = {"server": {"engine": "native"}, "options": {"reverse_proxy": {"enabled": False, "zones": [_zone("/a/")]}}}
        self.assertEqual(zone_engine_labels(OmegaServConfig.from_dict(data)), {})


if __name__ == "__main__":
    unittest.main()
