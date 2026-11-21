# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 10 : tunnel WebSocket natif (C17), cote Python (les essais de bout en bout, dans les deux
moteurs, sont dans tests/integration/test_native_proxy_websocket.py).

- une zone `websocket_enabled` est relayee par le natif : plus confiee a Python, plus de refus avec TLS direct ;
- le binaire doit annoncer `proxy_websocket` ;
- nouvelle option de zone `websocket_idle_timeout_seconds` (Q11) : 3 600 s par defaut, 0 = aucun delai, validee,
  ecrite dans l'instantane du natif ;
- reperage des trames (en-tetes seulement) et trames 1001, identiques au natif (tests/test_websocket.cpp)."""
from __future__ import annotations

import unittest

from omega_serv.application.server.engine_selection import (
    NATIVE_PROXY_GAPS,
    ZONE_WEBSOCKET,
    decide_engine,
    decide_proxy_zones,
    proxy_engine_problems,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.websocket import (
    WebSocketFrameTracker,
    close_frame_to_client,
    close_frame_to_server,
)
from omega_serv.domain.routing.proxy_zone import (
    ProxyZone,
    UpstreamTarget,
    parse_proxy_zones,
    validate_proxy_zone,
)
from omega_serv.infrastructure.server.native_engine import required_capabilities
from omega_serv.infrastructure.server.native_snapshot import proxy_section

_UPSTREAM = {"host": "10.0.0.5", "port": 80}


def _config(engine="native", websocket=True, tls_direct=False, **zone):
    data = {"server": {"engine": "native", "bind": "127.0.0.1", "port": 8080}, "options": {
        "reverse_proxy": {"enabled": True, "engine": engine, "zones": [
            {"url_prefix": "/ws/", "upstreams": [_UPSTREAM], "websocket_enabled": websocket, **zone}]}}}
    if tls_direct:
        data["tls"] = {"enabled": True, "mode": "direct"}
    return OmegaServConfig.from_dict(data)


def _frame(first: int, payload: bytes, masked: bool) -> bytes:
    mask_bit = 0x80 if masked else 0
    if len(payload) < 126:
        head = bytes((first, mask_bit | len(payload)))
    elif len(payload) < 65536:
        head = bytes((first, mask_bit | 126)) + len(payload).to_bytes(2, "big")
    else:
        head = bytes((first, mask_bit | 127)) + len(payload).to_bytes(8, "big")
    return head + (b"\x01\x02\x03\x04" if masked else b"") + payload


class TestWebSocketZoneIsNative(unittest.TestCase):
    def test_gap_is_lifted(self):
        self.assertNotIn(ZONE_WEBSOCKET, NATIVE_PROXY_GAPS)

    def test_websocket_zone_is_relayed_by_the_native_engine(self):
        for tls_direct in (False, True):  # TLS direct : avant le lot 10, refus (P7, zone confiee)
            with self.subTest(tls_direct=tls_direct):
                config = _config(tls_direct=tls_direct)
                self.assertEqual([(z.engine, z.reasons) for z in decide_proxy_zones(config)], [("native", ())])
                self.assertEqual(proxy_engine_problems(config).errors, ())
                self.assertEqual(decide_engine(config, None).effective, "native")

    def test_binary_must_announce_proxy_websocket(self):
        self.assertIn("proxy_websocket", required_capabilities(_config()))
        self.assertNotIn("proxy_websocket", required_capabilities(_config(websocket=False)))
        # auto : zones gardees en Python jusqu'au lot 11 ; depuis, auto relaie aussi le WebSocket.
        self.assertIn("proxy_websocket", required_capabilities(_config(engine="auto")))


class TestIdleTimeoutOption(unittest.TestCase):
    def test_default_parse_and_snapshot(self):
        self.assertEqual(ProxyZone(url_prefix="/ws/").websocket_idle_timeout_seconds, 3600.0)
        zone = parse_proxy_zones([{"url_prefix": "/ws/", "upstreams": [_UPSTREAM],
                                   "websocket_idle_timeout_seconds": 90}])[0]
        self.assertEqual(zone.websocket_idle_timeout_seconds, 90.0)
        section = proxy_section(_config(websocket_idle_timeout_seconds=1.5), security_stage=False, waf_filter=None)
        assert section is not None
        self.assertEqual(section["zones"][0]["websocket_idle_timeout_ms"], 1500)
        default = proxy_section(_config(), security_stage=False, waf_filter=None)
        assert default is not None
        self.assertEqual(default["zones"][0]["websocket_idle_timeout_ms"], 3_600_000)

    def test_validation(self):
        base = {"url_prefix": "/ws/", "upstreams": (UpstreamTarget(host="10.0.0.5", port=80),)}
        for value, valid in ((0, True), (1, True), (31_536_000, True), (-1, False), (31_536_001, False)):
            with self.subTest(value=value):
                reason = validate_proxy_zone(ProxyZone(**base, websocket_idle_timeout_seconds=value))
                self.assertEqual(reason is None, valid, reason)


class TestFrameTracker(unittest.TestCase):
    def test_boundaries_one_byte_at_a_time(self):
        first = _frame(0x81, b"salut", masked=True)
        stream = first + _frame(0x82, b"x" * 300, False) + _frame(0x82, b"y" * 70000, True) + _frame(0x89, b"", False)
        tracker = WebSocketFrameTracker()
        boundaries = []
        for i in range(len(stream)):
            tracker.feed(stream[i:i + 1])
            if tracker.at_boundary:
                boundaries.append(i + 1)
        frame_ends = [len(first), len(first) + 304, len(first) + 304 + 70014, len(stream)]
        self.assertEqual(boundaries, frame_ends)
        self.assertTrue(tracker.can_send_close)
        tracker.feed(stream[:3])
        self.assertFalse(tracker.can_send_close)

    def test_close_already_sent_forbids_1001(self):
        tracker = WebSocketFrameTracker()
        tracker.feed(_frame(0x88, b"\x03\xe8", masked=False))
        self.assertTrue(tracker.at_boundary)
        self.assertTrue(tracker.close_seen)
        self.assertFalse(tracker.can_send_close)

    def test_close_frames_like_the_native_engine(self):
        self.assertEqual(close_frame_to_client(), b"\x88\x02\x03\xe9")
        self.assertEqual(close_frame_to_server(b"\x10\x20\x30\x40"),
                         b"\x88\x82\x10\x20\x30\x40" + bytes((0x03 ^ 0x10, 0xE9 ^ 0x20)))


if __name__ == "__main__":
    unittest.main()
