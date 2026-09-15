# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase 9 : rechargement a chaud borne (angle mort
§9.1) contre un serveur reel - verifie qu'un changement WAF est bien
pris en compte apres reload_server(), sans redemarrer le socket
d'ecoute (meme port avant/apres)."""
import asyncio
import http.client
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server, reload_server
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
        # Demarre SANS waf actif.
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

        # Le socket d'ecoute n'a pas change (meme port toujours joignable).
        self.assertEqual(self.server.sockets[0].getsockname()[1], self.port)

    async def test_dirlisting_enabled_via_reload_takes_effect_without_restart(self):
        # Retour utilisateur (guide d'aide, point 4) : "j'ai active le
        # dir listing, ca marchait pas, j'ai redemarre et ca marche" -
        # verifie ici qu'un simple reload_server() (SIGHUP) suffit deja
        # (route_request lit `self._config` a chaque requete, remplace
        # en bloc par reload_scoped) - un restart complet n'a jamais
        # ete necessaire pour cette option, contrairement a ce que
        # l'absence d'avertissement dans l'interface laissait croire.
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
        # Retour utilisateur (audit performance) : les regles de
        # controle d'acces sont desormais mises en cache a la
        # construction (parsees une seule fois, plus a chaque requete) -
        # verifie ici que reload_scoped() invalide bien ce cache, pour
        # qu'un changement via SIGHUP reste effectif immediatement,
        # jamais fige sur l'etat du premier demarrage.
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


if __name__ == "__main__":
    unittest.main()
