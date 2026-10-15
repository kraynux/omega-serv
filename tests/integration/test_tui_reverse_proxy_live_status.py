"""Bout en bout REEL (§22, reouverture) : un vrai TUI (Pilot) pilote
`ReverseProxyUpstreamStatusScreen`, qui appelle le VRAI
`infrastructure.proxy_admin.http_admin_client.call_admin_endpoint` (pas
un double), qui parle en HTTP reel a un VRAI `AsyncioHttpServer`
(`build_server()`) demarre dans ce meme test - les deux "processus"
restent logiquement separes (le TUI ne touche jamais l'etat memoire du
serveur directement, seulement via la route HTTP), exactement la
situation reelle que §18.3 a identifiee comme bloquante jusqu'ici."""
from __future__ import annotations

import asyncio
import http.client
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from textual.css.query import NoMatches
from textual.widgets import Button, DataTable

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.start_server import build_server
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import Option
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
from omega_serv.infrastructure.proxy_admin.http_admin_client import call_admin_endpoint
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.reverse_proxy_screen import ReverseProxyScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTuiReverseProxyLiveStatus(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self._upstream_servers: list[asyncio.AbstractServer] = []

    async def asyncTearDown(self):
        for server in self._upstream_servers:
            server.close()
            await server.wait_closed()
        if getattr(self, "real_server", None) is not None:
            await self.real_server.close()
        self._tmp.cleanup()

    async def _start_real_server_with_zone(self, upstream_port: int, *, cache_enabled: bool = False) -> None:
        container = DependencyContainer(project_root=self.root)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        load_result = load_config(container.configuration, container.config_file)
        assert load_result.config is not None
        new_options = dict(load_result.config.options)
        new_options["reverse_proxy"] = Option(
            name="reverse_proxy", enabled=True,
            settings={"zones": [{
                "url_prefix": "/api/", "cache_enabled": cache_enabled,
                "upstreams": [{"host": "127.0.0.1", "port": upstream_port}],
            }]},
        )
        new_options["trusted_proxy"] = Option(
            name="trusted_proxy", enabled=True, settings={"trusted_networks": ["127.0.0.1/32"]},
        )
        config = replace(
            load_result.config, options=new_options,
            server=replace(load_result.config.server, bind="127.0.0.1", port=0),
            security=replace(load_result.config.security, allowed_methods=("GET", "HEAD", "POST")),
        )
        container.configuration.save(container.config_file, config)

        self.real_server = build_server(config, self.root, LocalFilesystem(), FileLineLogger())
        await self.real_server.start()
        bound_port = self.real_server.sockets[0].getsockname()[1]

        # Reecrit le port REELLEMENT lie (ephemere, 0 a la saisie) dans la config sur
        # disque - le TUI lit ce fichier pour savoir quel port appeler (meme hypothese
        # qu'un vrai deploiement : le fichier de config reflete ou le service ecoute).
        final_config = replace(config, server=replace(config.server, port=bound_port))
        container.configuration.save(container.config_file, final_config)

    def _tui_container(self) -> DependencyContainer:
        return DependencyContainer(project_root=self.root, admin_request_runner=call_admin_endpoint)

    async def _open_reverse_proxy_screen(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        while not isinstance(pilot.app.screen, HomeScreen):
            await pilot.press("escape")
            await pilot.pause()
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
        pilot.app.screen.query_one("#reverse-proxy", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ReverseProxyScreen)

    async def _wait_for_status_row(self, pilot, *, expected_status: str) -> None:
        """Attente active (meme patron que test_tui_tls.py::_wait_for_generate_to_finish)
        plutot qu'une pause fixe - le worker `_refresh`/`_set_status` fait un VRAI
        aller-retour HTTP, dont la duree n'est pas garantie sous charge (suite
        complete). La table elle-meme peut ne pas encore exister au tout premier
        passage (l'ecran vient d'etre pousse, pas encore monte) - `NoMatches`
        traite comme "pas encore pret", jamais une erreur."""
        for _ in range(60):
            await pilot.pause()
            try:
                table = pilot.app.screen.query_one("#upstream-status-table", DataTable)
            except NoMatches:
                await asyncio.sleep(0.05)
                continue
            if table.row_count > 0 and table.get_row_at(0)[1] == expected_status:
                return
            await asyncio.sleep(0.05)
        self.fail(f"le statut attendu ({expected_status!r}) n'est jamais apparu dans la table")

    async def _wait_for_cache_ratio_containing(self, pilot, *, needle: str) -> None:
        for _ in range(60):
            await pilot.pause()
            try:
                text = str(pilot.app.screen.query_one("#cache-ratio").content)
            except NoMatches:
                await asyncio.sleep(0.05)
                continue
            if needle in text:
                return
            await asyncio.sleep(0.05)
        self.fail(f"le ratio cache n'a jamais contenu {needle!r}")

    async def test_live_status_shows_up_then_draining_then_automatic(self):
        upstream = await asyncio.start_server(
            lambda r, w: w.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"), "127.0.0.1", 0,
        )
        self._upstream_servers.append(upstream)
        upstream_port = upstream.sockets[0].getsockname()[1]
        await self._start_real_server_with_zone(upstream_port)

        app = OmegaServApp(self._tui_container())
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open_reverse_proxy_screen(pilot)
            table = pilot.app.screen.query_one("#proxy-zones-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#live-status", Button).press()
            await self._wait_for_status_row(pilot, expected_status="up")

            status_table = pilot.app.screen.query_one("#upstream-status-table", DataTable)
            self.assertEqual(status_table.row_count, 1)
            self.assertEqual(list(status_table.get_row_at(0)), [f"127.0.0.1:{upstream_port}", "up"])

            status_table.move_cursor(row=0)
            status_table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#draining", Button).press()
            await self._wait_for_status_row(pilot, expected_status="draining")
            self.assertEqual(list(status_table.get_row_at(0)), [f"127.0.0.1:{upstream_port}", "draining"])

            status_table.move_cursor(row=0)
            status_table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#clear", Button).press()
            await self._wait_for_status_row(pilot, expected_status="up")
            self.assertEqual(list(status_table.get_row_at(0)), [f"127.0.0.1:{upstream_port}", "up"])

    async def test_cache_screen_shows_live_hit_miss_ratio(self):
        """§22 reouverture - meme discipline bout en bout que ci-dessus,
        pour `ReverseProxyCacheScreen` : une vraie requete MISS puis une
        vraie requete HIT contre le vrai serveur, le ratio affiche par
        l'ecran doit refleter ces deux evenements reels."""
        upstream = await asyncio.start_server(
            lambda r, w: w.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"), "127.0.0.1", 0,
        )
        self._upstream_servers.append(upstream)
        upstream_port = upstream.sockets[0].getsockname()[1]
        await self._start_real_server_with_zone(upstream_port, cache_enabled=True)

        server_port = self.real_server.sockets[0].getsockname()[1]

        def _raw_request() -> None:
            conn = http.client.HTTPConnection("127.0.0.1", server_port, timeout=3)
            try:
                conn.request("GET", "/api/users")
                conn.getresponse().read()
            finally:
                conn.close()

        await asyncio.to_thread(_raw_request)
        await asyncio.to_thread(_raw_request)

        app = OmegaServApp(self._tui_container())
        async with app.run_test(size=(120, 50)) as pilot:
            await self._open_reverse_proxy_screen(pilot)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
            pilot.app.screen.query_one("#reverse-proxy-cache", Button).press()
            await self._wait_for_cache_ratio_containing(pilot, needle="hit(s)")

            ratio_text = str(pilot.app.screen.query_one("#cache-ratio").content)
            self.assertIn("1 hit(s)", ratio_text)
            self.assertIn("1 miss(es)", ratio_text)


if __name__ == "__main__":
    unittest.main()
