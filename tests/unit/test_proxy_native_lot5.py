# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 5 : ce que le superviseur exige du binaire (relais en flux) et le contrat HEALTH des
compteurs du pool et des nouveaux essais, identique des deux cotes (ipc.hpp / native_ipc.py)."""
import re
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.native_engine import required_capabilities

REPO = Path(__file__).resolve().parents[2]
IPC_HPP = REPO / "native" / "omega-http-core" / "src" / "ipc.hpp"
CONTROL_CPP = REPO / "native" / "omega-http-core" / "src" / "control.cpp"


def _config(proxy: dict | None) -> OmegaServConfig:
    zone = {"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 9000}]}
    options = {"reverse_proxy": {"enabled": True, "zones": [zone], **(proxy or {})}}
    return OmegaServConfig.from_dict({"server": {"engine": "native", "port": 8080}, "options": options})


class TestRequiredCapabilities(unittest.TestCase):
    def test_native_zone_requires_the_streaming_relay(self):
        # Un binaire du lot 4 repondait 502 aux reponses chunked : il fait desormais replier sur Python au demarrage.
        needed = required_capabilities(_config({"engine": "native"}))
        self.assertTrue({"proxy_relay", "proxy_stream"} <= needed)

    def test_handed_off_zone_does_not(self):
        needed = required_capabilities(_config({"engine": "python"}))  # zone confiee (auto : jusqu'au lot 11)
        self.assertNotIn("proxy_stream", needed)
        self.assertIn("handoff_done", needed)

    def test_binary_announces_it(self):
        self.assertIn('"proxy_stream"', CONTROL_CPP.read_text())


class TestHealthContract(unittest.TestCase):
    def test_pool_and_retry_tags_match_the_native_side(self):
        text = IPC_HPP.read_text()
        tags = {name: int(value) for name, value in re.findall(r"kHealth(\w+) = (\d+);", text)}
        self.assertEqual(tags["UpstreamRetries"], ipc.HEALTH_UPSTREAM_RETRIES)
        self.assertEqual(tags["UpstreamIdle"], ipc.HEALTH_UPSTREAM_IDLE)
        self.assertEqual(len(set(tags.values())), len(tags), "etiquettes HEALTH en double")


if __name__ == "__main__":
    unittest.main()
