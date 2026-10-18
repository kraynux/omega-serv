"""Blocklist sous var/lib/waf/ (2026-10-18) : un vrai serveur reprend l'ancienne
blocklist de secure/waf/ au demarrage et y ENREGISTRE ses auto-bans - avant, le
service systemd ne pouvait pas ecrire dans secure/ et aucun auto-ban n'etait
jamais persiste."""
from __future__ import annotations

import asyncio
import contextlib
import http.client
import io
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server, build_waf_collaborators
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class TestBlocklistUnderVar(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("ok")
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True)
        (rules / "p.json").write_text(json.dumps({"version": 1, "pack": "p", "enabled": True, "rules": [
            {"id": "P-1", "description": "", "scope": ["path"], "pattern": "/\\.env", "weight": 6}]}))
        self.legacy = self.root / "secure" / "waf" / "blocklist.json"
        self.legacy.write_text(json.dumps({"version": 1, "entries": [
            {"network": "203.0.113.9/32", "reason": "ancien ban", "created_at": "2026-10-01T00:00:00+00:00",
             "expires_at": None, "source": "manual"}]}))
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"waf": {"enabled": True, "mode": "block",
                                "reputation": {"enabled": True, "auto_block": True, "suspicious_threshold": 1},
                                "rules": {"paths": ["secure/waf/rules/p.json"]}}},
        })
        with contextlib.redirect_stderr(io.StringIO()) as self.stderr:
            self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            return response.status
        finally:
            conn.close()

    async def test_legacy_bans_migrated_and_auto_ban_persisted(self):
        target = self.root / "var" / "lib" / "waf" / "blocklist.json"
        self.assertIn("reprise", self.stderr.getvalue())
        self.assertEqual(await asyncio.to_thread(self._get, "/.env"), 403)
        ips = [e["network"] for e in json.loads(target.read_text())["entries"]]
        self.assertIn("203.0.113.9/32", ips, "ancien ban conserve")
        self.assertTrue(any(ip.startswith("127.0.0.1") for ip in ips), ips)
        self.assertEqual(await asyncio.to_thread(self._get, "/index.html"), 403, "client banni")
        self.assertEqual(json.loads(self.legacy.read_text())["entries"][0]["network"], "203.0.113.9/32")


class TestMagnetBlocklistSavedWithLegacyPath(unittest.TestCase):
    """Cas reel craftdark : l'ecran WAF Magnet a enregistre l'ancien chemin en
    toutes lettres - il doit quand meme suivre le nouveau defaut et etre repris."""

    def test_legacy_magnet_blocklist_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "secure" / "waf" / "scripts"
            scripts.mkdir(parents=True)
            shipped = Path(__file__).resolve().parents[2] / "secure" / "waf" / "scripts" / "waf.lua"
            (scripts / "waf.lua").write_text(shipped.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "secure" / "waf" / "magnet-blocklist.txt").write_text("198.51.100.7\n")
            config = OmegaServConfig.from_dict({
                "server": {"bind": "127.0.0.1", "port": 0},
                "options": {"waf": {"enabled": True, "mode": "block", "magnet": {
                    "enabled": True, "script": "secure/waf/scripts/waf.lua",
                    "paths": {"blocklist_file": "secure/waf/magnet-blocklist.txt"}}}},
            })
            with contextlib.redirect_stderr(io.StringIO()):
                build_waf_collaborators(config, root, LocalFilesystem(), SystemClock())
            migrated = root / "var" / "lib" / "waf" / "magnet-blocklist.txt"
            self.assertEqual(migrated.read_text(), "198.51.100.7\n")


if __name__ == "__main__":
    unittest.main()
