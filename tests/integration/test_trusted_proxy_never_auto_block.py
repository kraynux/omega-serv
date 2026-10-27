"""Bout en bout reel (OMEGA-SERV_A_FAIRE_APRES_TRADUCTIONS.md §2) : derriere
un proxy local (tailscale serve) avec `trusted_proxy` actif, une adresse
Tailscale ou locale transmise par X-Forwarded-For n'est JAMAIS bannie
automatiquement, une adresse publique l'est - via le vrai serveur, la vraie
resolution d'adresse et la vraie blocklist sur disque."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger

_PACK = {
    "version": 1, "pack": "test-hostile", "enabled": True,
    "rules": [{"id": "T1", "description": "chemin hostile", "scope": ["path"], "pattern": "/secret-x", "weight": 10}],
}


class TestTrustedProxyNeverAutoBlock(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("ok")
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True)
        (rules / "test-hostile.json").write_text(json.dumps(_PACK))
        self.server = None

    async def asyncTearDown(self):
        if self.server is not None:
            await self.server.close()
        self._tmp.cleanup()

    async def _start(self, trusted_proxy: bool) -> None:
        options = {
            "waf": {
                "enabled": True,
                "mode": "block",
                "rules": {"paths": ["secure/waf/rules/test-hostile.json"]},
                "reputation": {"enabled": True, "suspicious_threshold": 2, "auto_block": True},
            },
        }
        if trusted_proxy:
            options["trusted_proxy"] = {"enabled": True, "trusted_networks": ["127.0.0.1/32"]}
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": options,
        })
        self.server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def _get(self, path: str, forwarded_for: str) -> int:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(
            f"GET {path} HTTP/1.1\r\nHost: x\r\nX-Forwarded-For: {forwarded_for}\r\nConnection: close\r\n\r\n".encode()
        )
        await writer.drain()
        status_line = await reader.readline()
        await reader.read()
        writer.close()
        return int(status_line.split()[1])

    def _banned_networks(self) -> list[str]:
        path = self.root / "var" / "lib" / "waf" / "blocklist.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        entries = data.get("entries", data) if isinstance(data, dict) else data
        return [entry["network"] for entry in entries]

    async def _attack(self, forwarded_for: str) -> list[int]:
        return [await self._get("/secret-x", forwarded_for) for _ in range(4)]

    async def test_tailscale_and_lan_clients_are_refused_but_never_banned(self):
        await self._start(trusted_proxy=True)
        for client in ("100.101.102.103", "192.168.1.20"):
            statuses = await self._attack(client)
            self.assertEqual(set(statuses), {403}, client)
            self.assertEqual(await self._get("/index.html", client), 200, client)
        self.assertEqual(self._banned_networks(), [])

    async def test_public_client_is_banned(self):
        await self._start(trusted_proxy=True)
        await self._attack("203.0.113.9")
        self.assertTrue(any(n.startswith("203.0.113.9") for n in self._banned_networks()), self._banned_networks())
        self.assertNotEqual(await self._get("/index.html", "203.0.113.9"), 200)
        # La page d'erreur d'une IP bannie garde son style (decision 2026-10-26).
        self.assertEqual(await self._get("/.omega-serv-error-css/error-pages.css", "203.0.113.9"), 200)
        self.assertEqual(await self._get("/index.html", "100.101.102.103"), 200)


if __name__ == "__main__":
    unittest.main()
