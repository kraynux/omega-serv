"""Incident reel du 2026-10-18 (craftdark) : secure/waf/blocklist.json reecrit
en root:root 600 par un outil lance en root -> PermissionError a CHAQUE
requete, site entier en 502. Desormais une blocklist illisible ne fait
jamais tomber le serveur, et n'est jamais reecrite vide."""
import asyncio
import contextlib
import http.client
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
from omega_serv.infrastructure.waf.blocklist_store import (
    BlocklistUnreadableError,
    JsonBlocklistStore,
)


class _Clock:
    def now(self):
        return datetime(2026, 10, 18, tzinfo=timezone.utc)


@unittest.skipIf(os.getuid() == 0, "root lit un fichier en mode 000")
class TestStoreWithUnreadableFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "blocklist.json"
        self.store = JsonBlocklistStore(LocalFilesystem(), self.path, _Clock())
        self.store.add_entry(BlocklistEntry(network="198.51.100.7/32", reason="test", created_at="2026-10-18T00:00:00+00:00"))
        self.store.is_blocked("198.51.100.7")  # cache charge
        self.path.chmod(0o000)

    def tearDown(self):
        self.path.chmod(0o644)
        self._tmp.cleanup()

    def test_reads_keep_last_valid_list_and_report_once(self):
        os.utime(self.path)  # mtime change : force une relecture
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            for _ in range(5):
                self.assertIsNotNone(self.store.is_blocked("198.51.100.7"))
                self.assertIsNone(self.store.is_blocked("203.0.113.1"))
        self.assertEqual(stderr.getvalue().count("ERREUR blocklist illisible"), 1)

    def test_unchanged_file_is_safely_rewritten_from_the_cache(self):
        """Fichier inchange depuis la derniere lecture : le cache EST son contenu,
        l'ecriture est sure (et repare au passage les droits du fichier)."""
        self.store.add_entry(BlocklistEntry(network="203.0.113.1/32", reason="x", created_at="2026-10-18T00:00:00+00:00"))
        content = self.path.read_text()
        self.assertIn("198.51.100.7/32", content)
        self.assertIn("203.0.113.1/32", content)

    def test_changed_unreadable_file_refuses_writes_and_is_never_emptied(self):
        """Le cas de l'incident : le fichier a ete REECRIT par un autre (mtime change)
        puis est illisible - son contenu reel est inconnu, toute ecriture est refusee."""
        os.utime(self.path, (1, 1))
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(BlocklistUnreadableError):
                self.store.add_entry(BlocklistEntry(network="203.0.113.1/32", reason="x", created_at="2026-10-18T00:00:00+00:00"))
            with self.assertRaises(BlocklistUnreadableError):
                self.store.remove_entry("198.51.100.7/32")
        self.path.chmod(0o644)
        self.assertIn("198.51.100.7/32", self.path.read_text())

    def test_unreadable_from_the_start_is_empty_not_an_error(self):
        fresh = JsonBlocklistStore(LocalFilesystem(), self.path, _Clock())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(fresh.is_blocked("198.51.100.7"))


@unittest.skipIf(os.getuid() == 0, "root lit un fichier en mode 000")
class TestServerSurvivesUnreadableBlocklist(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("ok")
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True)
        (rules / "p.json").write_text(json.dumps({"version": 1, "pack": "p", "enabled": True, "rules": [
            {"id": "P-1", "description": "", "scope": ["path"], "pattern": "/\\.env", "weight": 6}]}))
        self.blocklist = self.root / "var" / "lib" / "waf" / "blocklist.json"
        self.blocklist.parent.mkdir(parents=True)
        self.blocklist.write_text('{"entries": []}')
        self.blocklist.chmod(0o000)  # comme root:root 600 vu par le compte du service
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"waf": {"enabled": True, "mode": "block", "on_internal_error": "fail-closed",
                                "reputation": {"enabled": True, "auto_block": True, "suspicious_threshold": 1},
                                "rules": {"paths": ["secure/waf/rules/p.json"]}}},
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self.blocklist.chmod(0o644)
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

    async def test_site_keeps_serving(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(await asyncio.to_thread(self._get, "/index.html"), 200)
            # declenche aussi un auto-ban impossible a ecrire : la requete repond quand meme
            self.assertEqual(await asyncio.to_thread(self._get, "/.env"), 403)
            self.assertEqual(await asyncio.to_thread(self._get, "/index.html"), 200)


if __name__ == "__main__":
    unittest.main()
