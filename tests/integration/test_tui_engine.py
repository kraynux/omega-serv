"""Interface du moteur HTTP (plan moteur C++ lot 9, Q6 tranchee le 2026-11-03) : choix du moteur dans
« Configuration de base », natif GRISE avec l'explication pour le degriser, ce qui tournera affiche (§25 : plus de
noms de niveaux), nombre de processus borne selon le moteur et le processeur, garde-fou a l'enregistrement d'un
reglage qui ferait perdre le natif (§16.5)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textual.widgets import Button, Input, RadioButton, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.platform_info import CpuInfo
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.base_config_screen import BaseConfigScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.engine_guard import save_guarded
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.limits_screen import LimitsScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]
def _cpu(physical: int) -> CpuInfo:
    return CpuInfo(logical=physical, physical=physical, affinity=physical, quota=None, load_1min=None, detected=True)


_DIRECT_TLS = {"enabled": True, "mode": "direct", "certificate_path": "secure/c.pem", "private_key_path": "secure/k.pem"}


class TestTuiEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(project_root=self.root)
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)

    def tearDown(self):
        self._tmp.cleanup()

    def _binary(self) -> None:
        (self.root / "bin").mkdir(exist_ok=True)
        binary = self.root / "bin" / "omega-http-core"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

    def _patch_config(self, **sections) -> None:
        data = json.loads(self.container.config_file.read_text())
        for name, value in sections.items():
            data.setdefault(name, {}).update(value)
        self.container.config_file.write_text(json.dumps(data))

    def _config(self):
        result = load_config(self.container.configuration, self.container.config_file)
        assert result.config is not None, result.errors
        return result.config

    async def _open(self, pilot, item: str) -> None:
        while not isinstance(pilot.app.screen, HomeScreen):
            await pilot.press("escape")
            await pilot.pause()
            if isinstance(pilot.app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
                await pilot.pause()
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
        pilot.app.screen.query_one(f"#{item}", Button).press()
        await pilot.pause()

    async def test_native_choice_greyed_with_how_to_enable_it(self):
        self._binary()
        self._patch_config(tls=_DIRECT_TLS, options={"upload": {"enabled": True}})
        async with OmegaServApp(self.container).run_test(size=(120, 60)) as pilot:
            await self._open(pilot, "base")
            screen = pilot.app.screen
            self.assertIsInstance(screen, BaseConfigScreen)
            self.assertTrue(screen.query_one("#engine-native", RadioButton).disabled)
            self.assertTrue(screen.query_one("#engine-python", RadioButton).value)
            hint = str(screen.query_one("#engine-hint", Static).content)
            self.assertIn("behind_proxy", hint)  # comment le degriser
            self.assertIn("moteur Python, 1 processus", hint)

    async def test_choosing_native_saves_it_and_shows_what_will_run(self):
        self._binary()
        async with OmegaServApp(self.container).run_test(size=(120, 60)) as pilot:
            await self._open(pilot, "base")
            screen = pilot.app.screen
            native = screen.query_one("#engine-native", RadioButton)
            self.assertFalse(native.disabled)
            native.value = True
            await pilot.pause()
            self.assertIn("moteur natif, 1 processus", str(screen.query_one("#engine-hint", Static).content))
            screen.query_one("#save", Button).press()
            await pilot.pause()
        self.assertEqual(self._config().server.engine, "native")

    async def test_missing_binary_greys_native(self):
        async with OmegaServApp(self.container).run_test(size=(120, 60)) as pilot:
            await self._open(pilot, "base")
            screen = pilot.app.screen
            self.assertTrue(screen.query_one("#engine-native", RadioButton).disabled)
            self.assertIn("binaire natif absent", str(screen.query_one("#engine-hint", Static).content))

    async def test_limits_screen_native_on_four_cores_allows_two(self):
        self._binary()
        self._patch_config(server={"engine": "native", "workers": 2})
        with mock.patch("omega_serv.interfaces.tui.screens.limits_screen.cpu_info", return_value=_cpu(4)):
            async with OmegaServApp(self.container).run_test(size=(120, 60)) as pilot:
                await self._open(pilot, "limits")
                screen = pilot.app.screen
                self.assertIsInstance(screen, LimitsScreen)
                self.assertIn("1 ou 2", str(screen.query_one("#workers-engine-hint", Static).content))
                result = str(screen.query_one("#workers-result", Static).content)
                self.assertIn("moteur natif, 2 processus", result)
                self.assertIn("sans effet", result)  # aucun controle de securite actif dans cette configuration

    async def test_limits_screen_native_on_two_cores_refuses_two(self):
        self._binary()
        self._patch_config(server={"engine": "native"})
        with mock.patch("omega_serv.interfaces.tui.screens.limits_screen.cpu_info", return_value=_cpu(2)):
            async with OmegaServApp(self.container).run_test(size=(120, 60)) as pilot:
                await self._open(pilot, "limits")
                screen = pilot.app.screen
                self.assertIn("1 seul", str(screen.query_one("#workers-engine-hint", Static).content))
                before = self.container.config_file.read_text()
                screen.query_one("#field-workers", Input).value = "2"
                await pilot.pause()
                self.assertIn("Trop élevé", str(screen.query_one("#workers-result", Static).content))
                screen.query_one("#save", Button).press()
                await pilot.pause()
                self.assertIn("Trop élevé", str(screen.query_one("#form-error", Static).content))
        self.assertEqual(self.container.config_file.read_text(), before)

    async def test_switching_to_native_with_too_many_processes_asks_to_bring_them_down(self):
        self._binary()
        self._patch_config(server={"workers": 2})
        with mock.patch("omega_serv.interfaces.tui.screens.base_config_screen.cpu_info", return_value=_cpu(2)):
            async with OmegaServApp(self.container).run_test(size=(120, 60)) as pilot:
                await self._open(pilot, "base")
                pilot.app.screen.query_one("#engine-native", RadioButton).value = True
                await pilot.pause()
                pilot.app.screen.query_one("#save", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, ConfirmScreen)
                self.assertIn("ramenant à 1", str(pilot.app.screen.query("Static").last().content))
                pilot.app.screen.query_one("#confirm", Button).press()
                await pilot.pause()
        config = self._config()
        self.assertEqual((config.server.engine, config.server.workers), ("native", 1))

    async def test_saving_a_setting_that_loses_native_asks_first(self):
        self._binary()
        self._patch_config(server={"engine": "native"}, tls=_DIRECT_TLS)
        previous = self._config()
        data = json.loads(self.container.config_file.read_text())
        data.setdefault("options", {})["upload"] = {"enabled": True}
        new = OmegaServConfig.from_dict(data)
        saved: list[bool] = []
        async with OmegaServApp(self.container).run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            save_guarded(pilot.app.screen, self.container, previous, new, lambda: saved.append(True))
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertIn("behind_proxy", str(pilot.app.screen.query("Static").last().content))
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertEqual(saved, [])
            self.assertFalse(self._config().option_enabled("upload"))
            save_guarded(pilot.app.screen, self.container, previous, new, lambda: saved.append(True))
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
        self.assertEqual(saved, [True])
        self.assertTrue(self._config().option_enabled("upload"))
