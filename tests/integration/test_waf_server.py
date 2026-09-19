"""Tests d'integration Phase 5 (WAF) : serveur reel, connexions TCP
reelles sur 127.0.0.1, aucun mock - meme discipline que
test_static_server.py."""
import asyncio
import http.client
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger

_SQLI_PACK = {
    "version": 1,
    "pack": "body-sqli",
    "enabled": True,
    "rules": [
        {"id": "SQLI-001", "description": "Union select", "scope": ["query"], "pattern": r"union\s+select", "weight": 5},
    ],
}


class _WafServerTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello world")

        rules_dir = self.root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "body-sqli.json").write_text(json.dumps(_SQLI_PACK))

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def _start(self, waf_settings: dict):
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"waf": {"enabled": True, **waf_settings}},
        })
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    def _request_sync(self, method, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, dict(resp.getheaders()), data
        finally:
            conn.close()

    async def _request(self, method, path, headers=None):
        return await asyncio.to_thread(self._request_sync, method, path, headers)


class TestWafSignatureBlocking(_WafServerTestCase):
    async def test_clean_request_passes(self):
        await self._start({"mode": "block", "rules": {"paths": ["secure/waf/rules/body-sqli.json"]}})
        status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)

    async def test_sqli_query_blocked_in_block_mode(self):
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
        })
        status, _, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(status, 403)

    async def test_sqli_query_only_logged_in_log_only_mode(self):
        await self._start({
            "mode": "log-only",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
        })
        status, _, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(status, 200)
        alert_log = self.root / "var" / "log" / "waf-alerts.log"
        self.assertTrue(alert_log.exists())
        record = json.loads(alert_log.read_text().splitlines()[-1])
        self.assertEqual(record["rules"], ["SQLI-001"])

    async def test_healthz_excluded_even_with_malicious_query(self):
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 1},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            "exclusions": {"path_prefixes": ["/healthz"]},
        })
        status, _, _ = await self._request("GET", "/healthz?q=union%20select%201")
        self.assertEqual(status, 200)


class TestWafBlocklist(_WafServerTestCase):
    async def test_blocklisted_ip_gets_403(self):
        blocklist_path = self.root / "secure" / "waf" / "blocklist.json"
        blocklist_path.write_text(json.dumps({
            "version": 1,
            "entries": [{"network": "127.0.0.1/32", "reason": "test", "created_at": "2026-09-05T00:00:00+00:00", "source": "manual"}],
        }))
        await self._start({"rules": {"paths": ["secure/waf/rules/body-sqli.json"]}})
        status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 403)


class TestWafRateLimit(_WafServerTestCase):
    async def test_rate_limit_blocks_after_quota_exceeded(self):
        await self._start({
            "rate_limit": {"enabled": True, "global": {"requests": 1, "window_seconds": 60}},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
        })
        status1, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status1, 200)
        status2, headers2, _ = await self._request("GET", "/index.html")
        self.assertEqual(status2, 429)
        self.assertIn("Retry-After", headers2)


if __name__ == "__main__":
    unittest.main()
