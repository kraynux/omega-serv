# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.security.simulate_waf_request import simulate_waf_request
from omega_serv.application.server.start_server import build_waf_collaborators
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

_SQLI_PACK = {
    "version": 1, "pack": "body-sqli", "enabled": True,
    "rules": [{"id": "SQLI-001", "description": "", "scope": ["query"], "pattern": r"union\s+select", "weight": 5}],
}


class TestSimulateWafRequest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        rules_dir = self.root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "body-sqli.json").write_text(json.dumps(_SQLI_PACK))
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def _waf(self, mode="block", block_threshold=5):
        from datetime import datetime, timezone

        class _Clock:
            def now(self):
                return datetime(2026, 9, 5, tzinfo=timezone.utc)

        config = OmegaServConfig.from_dict({
            "options": {"waf": {
                "enabled": True, "mode": mode,
                "scoring": {"block_threshold": block_threshold},
                "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            }},
        })
        return build_waf_collaborators(config, self.root, self.filesystem, _Clock())

    def test_clean_request_allowed(self):
        report = simulate_waf_request("GET", "/x", "", "", "203.0.113.1", self._waf())
        self.assertEqual(report.decision.action, "allow")

    def test_malicious_query_blocked(self):
        report = simulate_waf_request("GET", "/x", "id=1 union select pwd", "", "203.0.113.1", self._waf())
        self.assertEqual(report.decision.action, "block")
        self.assertEqual(report.decision.status_code, 403)
        self.assertIn("SQLI-001", [f.rule_id for f in report.decision.findings])

    def test_log_only_mode_never_blocks(self):
        report = simulate_waf_request("GET", "/x", "id=1 union select pwd", "", "203.0.113.1", self._waf(mode="log-only"))
        self.assertEqual(report.decision.action, "log")


if __name__ == "__main__":
    unittest.main()
