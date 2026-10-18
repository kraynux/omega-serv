"""Tests d'integration Phase 9 : rechargement a chaud borne (angle mort
§9.1) contre un serveur reel - verifie qu'un changement WAF est bien
pris en compte apres reload_server(), sans redemarrer le socket
d'ecoute (meme port avant/apres)."""
import asyncio
import http.client
import json
import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import (
    build_server,
    reload_server,
    try_reload_server,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger

_SQLI_PACK = {
    "version": 1, "pack": "body-sqli", "enabled": True,
    "rules": [{"id": "SQLI-001", "description": "", "scope": ["query"], "pattern": r"union\s+select", "weight": 5}],
}


class TestReloadScoped(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("ok")
        rules_dir = self.root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "body-sqli.json").write_text(json.dumps(_SQLI_PACK))

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.config = OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 0}})
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    def _request_sync(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            resp.read()
            return resp.status
        finally:
            conn.close()

    async def _request(self, path):
        return await asyncio.to_thread(self._request_sync, path)

    async def test_waf_enabled_via_reload_takes_effect_without_restart(self):
        status_before = await self._request("/index.html?q=union%20select%201")
        self.assertEqual(status_before, 200)  # WAF pas encore actif

        new_config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": self.config.server.port},
            "options": {"waf": {
                "enabled": True, "mode": "block", "scoring": {"block_threshold": 5},
                "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            }},
        })
        reload_server(self.server, new_config, self.root, self.filesystem)

        status_after = await self._request("/index.html?q=union%20select%201")
        self.assertEqual(status_after, 403)

        self.assertEqual(self.server.sockets[0].getsockname()[1], self.port)

    async def test_dirlisting_enabled_via_reload_takes_effect_without_restart(self):
        public_dir = self.root / "webroot" / "public"
        public_dir.mkdir()
        (public_dir / "report.txt").write_text("x")

        status_before = await self._request("/public/")
        self.assertEqual(status_before, 404)

        new_config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": self.config.server.port},
            "options": {"dirlisting": {"enabled": True, "zone_prefixes": ["/public/"]}},
        })
        reload_server(self.server, new_config, self.root, self.filesystem)

        status_after = await self._request("/public/")
        self.assertEqual(status_after, 200)
        self.assertEqual(self.server.sockets[0].getsockname()[1], self.port)

    async def test_access_control_deny_via_reload_takes_effect_without_restart(self):
        status_before = await self._request("/index.html")
        self.assertEqual(status_before, 200)

        new_config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": self.config.server.port},
            "options": {"access_control": {"enabled": True, "list": [{"path_prefix": "/index.html", "verdict": "deny"}]}},
        })
        reload_server(self.server, new_config, self.root, self.filesystem)

        status_after = await self._request("/index.html")
        self.assertEqual(status_after, 403)
        self.assertEqual(self.server.sockets[0].getsockname()[1], self.port)


class _KeywordListServerCase(unittest.IsolatedAsyncioTestCase):
    """Serveur reel avec une liste de chemins hostile (seuil de recidive 2)."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("ok")
        keywords_dir = self.root / "secure" / "waf" / "rules" / "keywords"
        keywords_dir.mkdir(parents=True)
        (keywords_dir / "sensitive-paths-hostile.txt").write_text("# test\n/.env\n")

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"waf": {
                "enabled": True, "mode": "block",
                "reputation": {"enabled": True, "auto_block": True},
                "rules": {"keyword_lists": [{
                    "id": "sensitive-paths-hostile", "scope": ["path"], "match": "path",
                    "file": "secure/waf/rules/keywords/sensitive-paths-hostile.txt", "weight": 6,
                    "escalation_threshold": 2, "escalation_window_seconds": 600,
                }]},
            }},
        })
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    def _request_sync(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            resp.read()
            return resp.status
        finally:
            conn.close()

    async def _request(self, path):
        return await asyncio.to_thread(self._request_sync, path)


class TestReloadKeepsRecidiveCounters(_KeywordListServerCase):
    """OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.12 : un SIGHUP (declenche
    a chaque enregistrement depuis l'editeur) ne doit PAS remettre a zero
    les recidives en cours. Verifie aussi de bout en bout le garde-fou
    §3.14-a : sans trusted_proxy, 127.0.0.1 n'est PAS exempte d'auto-ban."""

    async def test_recidive_survives_reload(self):
        self.assertEqual(await self._request("/.env"), 403)       # 1/2 : refuse, pas encore banni
        self.assertEqual(await self._request("/index.html"), 200)

        reload_server(self.server, self.config, self.root, self.filesystem)

        self.assertEqual(await self._request("/.env"), 403)       # 2/2 apres reload : ban
        self.assertEqual(await self._request("/index.html"), 403, "IP bannie : le compteur a survecu au reload")
        blocklist = json.loads((self.root / "var" / "lib" / "waf" / "blocklist.json").read_text())
        self.assertIn("sensitive-paths-hostile", json.dumps(blocklist))


class TestFailedReloadIsReportedAndKeepsOldRules(_KeywordListServerCase):
    """§3.8 : un rechargement qui echoue est SIGNALE (jamais silencieux) et
    laisse le serveur strictement inchange."""

    def _list_file(self):
        return self.root / "secure" / "waf" / "rules" / "keywords" / "sensitive-paths-hostile.txt"

    async def test_unreadable_list_refused_old_rules_kept(self):
        if os.getuid() == 0:
            self.skipTest("root lit un fichier en mode 000")
        self._list_file().chmod(0o000)
        try:
            error = try_reload_server(self.server, self.config, self.root, self.filesystem)
        finally:
            self._list_file().chmod(0o644)
        self.assertIsNotNone(error)
        self.assertEqual(await self._request("/.env"), 403, "les anciennes regles bloquent toujours")

    async def test_invalid_list_refused_with_line_number(self):
        self._list_file().write_text("/.env\n/robots.txt\n")
        error = try_reload_server(self.server, self.config, self.root, self.filesystem)
        self.assertIn("ligne 2", error)
        self.assertEqual(await self._request("/.env"), 403)
        self.assertEqual(await self._request("/robots.txt"), 404, "la liste invalide n'a pas ete chargee")

    async def test_successful_reload_returns_none(self):
        self.assertIsNone(try_reload_server(self.server, self.config, self.root, self.filesystem))


if __name__ == "__main__":
    unittest.main()
