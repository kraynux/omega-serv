"""Active Securite -> INTERVENTION MANUELLE (2026-11-06) : le cadre et ses trois boutons, un ban pose par l'ecran
Bannir (vraie blocklist sur disque), sa levee par Debannir (qui ignore les autres bans) et l'export TXT de Statut."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textual.widgets import Button, DataTable, Input, Select

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.server.start_server import build_blocklist_port
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.active_defense_menu_screen import ActiveDefenseMenuScreen
from omega_serv.interfaces.tui.screens.ban_status_screen import BanStatusScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.manual_ban_screen import ManualBanScreen
from omega_serv.interfaces.tui.screens.manual_unban_screen import ManualUnbanScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen


class TestManualIntervention(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        self.container = DependencyContainer(
            project_root=self.root,
            blocklist_port_factory=lambda cfg, fs, root, clock: build_blocklist_port(cfg, root, fs, clock),
        )
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)
        now = datetime.now(timezone.utc)
        self.blocklist = self.root / "var" / "lib" / "waf" / "blocklist.json"
        self.blocklist.parent.mkdir(parents=True)
        self.blocklist.write_text(json.dumps({"version": 1, "entries": [{
            "network": "186.247.44.146/32", "reason": "omega-jail:omega-serv-active-defense",
            "created_at": now.isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat(), "source": "manual",
        }]}))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _entries(self) -> list[dict]:
        return json.loads(self.blocklist.read_text())["entries"]

    async def _home(self, pilot) -> None:
        while not isinstance(pilot.app.screen, HomeScreen):
            await pilot.press("escape")
            await pilot.pause()
            if isinstance(pilot.app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
                await pilot.pause()

    async def test_menu_has_the_intervention_frame(self):
        async with OmegaServApp(self.container).run_test(size=(100, 45)) as pilot:
            await self._home(pilot)
            pilot.app.push_screen(ActiveDefenseMenuScreen(container=self.container))
            await pilot.pause()
            frame = pilot.app.screen.query_one(".omega-intervention-menu")
            self.assertEqual(frame.border_title, "INTERVENTION MANUELLE")
            self.assertEqual([b.id for b in frame.query(Button)],
                             ["intervention-ban", "intervention-unban", "intervention-status"])
            for button_id, screen_class in (("intervention-ban", ManualBanScreen),
                                            ("intervention-unban", ManualUnbanScreen),
                                            ("intervention-status", BanStatusScreen)):
                pilot.app.screen.query_one(f"#{button_id}", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, screen_class)
                pilot.app.pop_screen()
                await pilot.pause()

    async def test_ban_then_unban_through_the_screens(self):
        async with OmegaServApp(self.container).run_test(size=(100, 45)) as pilot:
            await self._home(pilot)
            pilot.app.push_screen(ManualBanScreen(container=self.container))
            await pilot.pause()
            screen = pilot.app.screen
            screen.query_one("#ban-ip", Input).value = "203.0.113.0/24"
            screen.query_one("#ban", Button).press()
            await pilot.pause()
            self.assertEqual(len(self._entries()), 1)  # reseau refuse

            screen.query_one("#ban-ip", Input).value = "203.0.113.7"
            screen.query_one("#ban-reason", Input).value = "scan agressif"
            screen.query_one("#ban-duration", Select).value = "3600"
            screen.query_one("#ban", Button).press()
            await pilot.pause()
            banned = [e for e in self._entries() if e["network"] == "203.0.113.7/32"]
            self.assertEqual(len(banned), 1)
            self.assertEqual((banned[0]["origin"], banned[0]["reason"]), ("intervention", "scan agressif"))

            screen.query_one("#ban-ip", Input).value = "192.168.1.20"
            screen.query_one("#ban", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)  # adresse privee : confirmation
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertFalse(any(e["network"] == "192.168.1.20/32" for e in self._entries()))
            pilot.app.pop_screen()
            await pilot.pause()

            pilot.app.push_screen(ManualUnbanScreen(container=self.container))
            await pilot.pause()
            table = pilot.app.screen.query_one("#unban-table", DataTable)
            self.assertEqual(table.row_count, 1)  # le ban omega-jail n'apparait pas
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#unban", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual([e["network"] for e in self._entries()], ["186.247.44.146/32"])

    async def test_status_lists_every_origin_and_exports_txt(self):
        async with OmegaServApp(self.container).run_test(size=(100, 45)) as pilot:
            await self._home(pilot)
            pilot.app.push_screen(BanStatusScreen(container=self.container))
            await pilot.pause()
            screen = pilot.app.screen
            self.assertEqual(screen.query_one("#status-table", DataTable).row_count, 1)
            screen.query_one("#export-format", Select).value = "txt-active"
            screen.query_one("#export", Button).press()
            await pilot.pause()
            exports = list(self.container.default_exports_dir.glob("omega-serv-bans-active.*.txt"))
            self.assertEqual(len(exports), 1)
            lines = [line for line in exports[0].read_text().splitlines() if not line.startswith("#")]
            self.assertEqual(lines, ["186.247.44.146"])


if __name__ == "__main__":
    unittest.main()
