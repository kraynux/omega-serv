# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 5 (P4, D36) : refus que le moteur natif decide seul sur une zone qu'il relaie, quand le
controle de securite est indisponible en `fail-open` - meme ligne `waf-alerts` que le moteur Python
(`_log_waf_alert`), comme pour le statique (lot 1N) : 451 d'une adresse bannie, 429 d'une limite de debit deja
mesuree. Le backend n'est jamais atteint pour une requete refusee ; une panne en `fail-closed` (503) n'ecrit aucune
alerte. Moteur natif lance sans canal de securite (aucun processus Python), comme les tests du lot 1N."""
from __future__ import annotations

import http.client
import json
import shutil
import socket
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.logging.waf_alert_format import WafAlertEntry, format_waf_alert_line
from omega_serv.domain.security.waf.config import WafLoggingConfig
from omega_serv.domain.security.waf.entities import WafDecision
from omega_serv.infrastructure.server.native_engine import NativeEngine
from tests.integration.proxy_harness import NATIVE_BINARY, ScriptedBackend

REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeRefusalsOnRelayedZone(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        for folder in ("webroot", "var/log", "var/run", "var/lib/waf"):
            (self.root / folder).mkdir(parents=True)
        (self.root / "webroot" / "index.html").write_text("site")
        self.rules = self.root / "rules.json"
        shutil.copy(next(p for p in sorted((REPO / "secure" / "waf" / "rules").glob("*.json"))
                         if p.name != "custom.json"), self.rules)
        self.backend = ScriptedBackend()
        self.addCleanup(self.backend.stop)
        self.listen = socket.create_server(("127.0.0.1", 0))
        self.addCleanup(self.listen.close)
        self.port = self.listen.getsockname()[1]

    def _start(self, waf: dict) -> NativeEngine:
        zone = {"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": self.backend.port}]}
        config = OmegaServConfig.from_dict({"server": {"engine": "native", "port": self.port}, "options": {
            "waf": {"enabled": True, "rules": {"paths": [str(self.rules)]}, **waf},
            "reverse_proxy": {"enabled": True, "engine": "native", "zones": [zone]}}})
        engine = NativeEngine(NATIVE_BINARY, self.root, threads=1)
        engine.start(config, [self.listen.fileno()])  # aucun canal de securite
        self.addCleanup(engine.stop, 2.0)
        return engine

    def _get(self, path: str) -> int:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            return response.status
        finally:
            conn.close()

    def _alerts(self) -> list[tuple[dict, str]]:
        path = self.root / "var" / "log" / "waf-alerts.log"
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        return [(json.loads(line), line) for line in lines]

    @staticmethod
    def _python_line(record: dict, stage: str, status: int, path: str) -> str:
        """La ligne que _log_waf_alert aurait ecrite (horodatage et duree repris du natif)."""
        entry = WafAlertEntry(
            request_id=record["request_id"], timestamp=datetime.fromisoformat(record["timestamp"]),
            remote_ip="127.0.0.1", method="GET", path=path, user_agent=None,
            decision=WafDecision(action="block", status_code=status, score=0, log_level="warning", stage=stage),
            duration_ms=record["duration_ms"])
        return format_waf_alert_line(entry, WafLoggingConfig())

    def test_banned_address_gets_451_and_the_python_alert_line(self):
        (self.root / "var" / "lib" / "waf" / "blocklist.json").write_text(json.dumps({"version": 1, "entries": [{
            "network": "127.0.0.1/32", "reason": "test", "created_at": "2026-11-13T00:00:00+00:00",
            "expires_at": None, "source": "manual"}]}))
        self._start({"on_internal_error": "fail-open"})
        self.assertEqual(self._get("/api/ok"), 451)
        self.assertEqual(self.backend.hits_for("/api/ok"), 0)
        alerts = self._alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][1], self._python_line(alerts[0][0], "blocklist", 451, "/api/ok"))

    def test_measured_rate_limit_gets_429_and_the_python_alert_line(self):
        self._start({"on_internal_error": "fail-open",
                     "rate_limit": {"enabled": True, "global": {"requests": 2, "window_seconds": 60}}})
        self.assertEqual([self._get("/api/ok") for _ in range(3)], [200, 200, 429])
        self.assertEqual(self.backend.hits_for("/api/ok"), 2)  # relayees sans controle (fail-open), la 3e jamais
        alerts = self._alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][1], self._python_line(alerts[0][0], "rate_limit", 429, "/api/ok"))

    def test_fail_closed_outage_writes_no_alert(self):
        self._start({"on_internal_error": "fail-closed"})
        self.assertEqual(self._get("/api/ok"), 503)
        self.assertEqual(self.backend.hits_for("/api/ok"), 0)
        self.assertEqual(self._alerts(), [])


if __name__ == "__main__":
    unittest.main()
