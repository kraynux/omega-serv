"""Tests d'integration Phase 4 de l'assistant TLS (etude
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md) : sous-ecran Let's Encrypt
(Certbot). `certificate_tool_factory` reste le vrai OpensslCertificateTool
(meme discipline que test_tui_tls.py) mais `acme_client_factory` est
FAUX ici - jamais de vrai `certbot`/reseau dans une suite automatisee.
Le faux runner ecrit un vrai certificat auto-signe (openssl reel) sous
`<config-dir>/live/<domaine>/` pour simuler fidelement ce que ferait
Certbot, afin que l'import qui suit (openssl reel : keys_match/
inspect_certificate) reste teste avec de vraies donnees."""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Checkbox, Input, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.lets_encrypt_screen import LetsEncryptScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.screens.tls_menu_screen import TlsMenuScreen
from omega_serv.ports.process_runner_port import ProcessResult

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OPENSSL_MISSING = shutil.which("openssl") is None


def _build_certificate_tool():
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
    from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

    return OpensslCertificateTool(SubprocessRunner())


class _FakeCertbotRunner:
    """Simule Certbot : ecrit un vrai couple cle/certificat (openssl
    reel) sous `<config-dir>/live/<domaine>/` quand `succeeds` est vrai,
    n'ecrit rien sinon (simule un echec Certbot, ex. rate-limit)."""

    def __init__(self, letsencrypt_dir: Path, domain: str, *, succeeds: bool = True, stderr: str = "") -> None:
        self._letsencrypt_dir = letsencrypt_dir
        self._domain = domain
        self._succeeds = succeeds
        self._stderr = stderr
        self.calls: list[list[str]] = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append(args)
        if self._succeeds:
            live_dir = self._letsencrypt_dir / "config" / "live" / self._domain
            live_dir.mkdir(parents=True, exist_ok=True)
            tool = _build_certificate_tool()
            params = SelfSignedCertParams(common_name=self._domain, san_dns=(self._domain,))
            tool.generate_self_signed(params, live_dir / "privkey.pem", live_dir / "fullchain.pem")
            return ProcessResult(returncode=0, stdout="", stderr="")
        return ProcessResult(returncode=1, stdout="", stderr=self._stderr)

    def run_interactive(self, args):
        raise NotImplementedError


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestTuiLetsEncrypt(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.domain = "example.dynu.com"
        self.letsencrypt_dir = self.root / "secure" / "certificates" / "letsencrypt"

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, *, succeeds: bool = True, stderr: str = "") -> DependencyContainer:
        self._acme_runner = _FakeCertbotRunner(self.letsencrypt_dir, self.domain, succeeds=succeeds, stderr=stderr)
        return DependencyContainer(
            project_root=self.root, certificate_tool_factory=_build_certificate_tool,
            acme_client_factory=lambda: self._acme_runner,
        )

    def _generate_config(self, container: DependencyContainer) -> None:
        generate_default_config(container.configuration, container.filesystem, container.config_file)

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def _open_tls_menu(self, pilot) -> None:
        while not isinstance(pilot.app.screen, HomeScreen):
            await pilot.press("escape")
            await pilot.pause()
            if isinstance(pilot.app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
                await pilot.pause()
        pilot.app.screen.query_one("#server-config", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ServerConfigMenuScreen)
        pilot.app.screen.query_one("#tls", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, TlsMenuScreen)

    async def _enable_tls_direct(self, pilot) -> None:
        pilot.app.screen.query_one("#toggle", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#mode-input", Input).value = "direct"
        pilot.app.screen.query_one("#enable", Button).press()
        await pilot.pause()
        pilot.app._notifications.clear()
        await pilot.press("escape")
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, TlsMenuScreen)

    async def _wait_for_request_to_finish(self, pilot) -> None:
        for _ in range(40):
            await pilot.pause()
            if not pilot.app.screen.query_one("#request", Button).disabled:
                return
            await asyncio.sleep(0.05)
        self.fail("la demande Let's Encrypt ne s'est jamais terminee")

    async def test_back_button_returns_to_tls_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#lets-encrypt", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LetsEncryptScreen)
            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TlsMenuScreen)

    async def test_rejects_empty_domain_without_showing_confirm_dialog(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#lets-encrypt", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#request", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LetsEncryptScreen)
            self.assertIn("vide", str(pilot.app.screen.query_one("#form-error").content))

    async def test_successful_flow_installs_certificate_and_shows_summary_first(self):
        container = self._container(succeeds=True)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#lets-encrypt", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#domain-input", Input).value = self.domain
            pilot.app.screen.query_one("#request", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            confirm_text = "\n".join(str(s.content) for s in pilot.app.screen.query(Static))
            self.assertIn(self.domain, confirm_text)

            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_request_to_finish(pilot)
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

        argv = self._acme_runner.calls[0]
        self.assertNotIn("/etc/letsencrypt", " ".join(argv))
        self.assertIn("--staging", argv)
        cert_path = self.root / "secure" / "certificates" / "server" / "server.pem"
        key_path = self.root / "secure" / "certificates" / "server" / "server.key"
        self.assertTrue(cert_path.exists())
        self.assertTrue(key_path.exists())
        hook_path = self.letsencrypt_dir / "hooks" / f"deploy-{self.domain}.sh"
        self.assertTrue(hook_path.exists())

    async def test_declining_confirm_dialog_runs_nothing(self):
        container = self._container(succeeds=True)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#lets-encrypt", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#domain-input", Input).value = self.domain
            pilot.app.screen.query_one("#request", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, LetsEncryptScreen)
        self.assertEqual(self._acme_runner.calls, [])

    async def test_certbot_failure_reported_without_crashing(self):
        container = self._container(succeeds=False, stderr="rate limited")
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#lets-encrypt", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#domain-input", Input).value = self.domain
            pilot.app.screen.query_one("#request", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_request_to_finish(pilot)
            self.assertIn("rate limited", str(pilot.app.screen.query_one("#form-error").content))

    async def test_staging_can_be_disabled(self):
        container = self._container(succeeds=True)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#lets-encrypt", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#domain-input", Input).value = self.domain
            pilot.app.screen.query_one("#staging-checkbox", Checkbox).value = False
            pilot.app.screen.query_one("#request", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_request_to_finish(pilot)

        argv = self._acme_runner.calls[0]
        self.assertNotIn("--staging", argv)

    async def test_warns_restart_when_tls_already_enabled(self):
        container = self._container(succeeds=True)
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            await self._enable_tls_direct(pilot)

            pilot.app.screen.query_one("#lets-encrypt", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#domain-input", Input).value = self.domain
            pilot.app.screen.query_one("#request", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_request_to_finish(pilot)
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
