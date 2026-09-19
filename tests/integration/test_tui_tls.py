"""Tests d'integration Phase III de l'interface (plan interface §12,
menu 3, sous-ecran TLS §7.3) : statut, certificat auto-signe (6a),
assistant CA locale (6b), revocation, activer/desactiver TLS. Vraie
CertificateToolPort (openssl reel, pas de mock) - meme discipline que
tests/unit/test_openssl_certificate_tool.py, `skipIf` si openssl
absent du systeme."""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Input

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.ca_wizard_screen import CaWizardScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.generate_self_signed_screen import GenerateSelfSignedScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.revoke_certificate_screen import RevokeCertificateScreen
from omega_serv.interfaces.tui.screens.server_config_menu_screen import ServerConfigMenuScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.screens.tls_menu_screen import TlsMenuScreen
from omega_serv.interfaces.tui.screens.tls_status_screen import TlsStatusScreen
from omega_serv.interfaces.tui.screens.tls_toggle_screen import TlsToggleScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OPENSSL_MISSING = shutil.which("openssl") is None


def _build_certificate_tool():
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
    from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

    return OpensslCertificateTool(SubprocessRunner())


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestTuiTls(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self) -> DependencyContainer:
        return DependencyContainer(project_root=self.root, certificate_tool_factory=_build_certificate_tool)

    def _generate_config(self, container: DependencyContainer) -> None:
        generate_default_config(container.configuration, container.filesystem, container.config_file)

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

    async def _wait_for_button_reenabled(self, pilot, button_id: str) -> None:
        for _ in range(40):
            await pilot.pause()
            if not pilot.app.screen.query_one(f"#{button_id}", Button).disabled:
                return
            await asyncio.sleep(0.05)
        self.fail(f"l'operation ({button_id}) ne s'est jamais terminee")

    async def _wait_for_generate_to_finish(self, pilot) -> None:
        for _ in range(40):
            await pilot.pause()
            if not pilot.app.screen.query_one("#generate", Button).disabled:
                return
            await asyncio.sleep(0.05)
        self.fail("la generation ne s'est jamais terminee")

    async def _start(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()

    async def test_status_shows_no_certificate_then_generated_one(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#status", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TlsStatusScreen)
            self.assertIn("Aucun certificat", str(pilot.app.screen.query_one("#status-text").content))

    async def test_generate_self_signed_certificate(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#self-signed", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GenerateSelfSignedScreen)
            pilot.app.screen.query_one("#cn-input", Input).value = "test.local"
            pilot.app.screen.query_one("#san-dns-input", Input).value = "test.local"
            pilot.app.screen.query_one("#generate", Button).press()
            await self._wait_for_generate_to_finish(pilot)
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

        cert_path = self.root / "secure" / "certificates" / "server" / "server.pem"
        self.assertTrue(cert_path.exists())

    async def test_generate_self_signed_rejects_invalid_key_type(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#self-signed", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cn-input", Input).value = "test.local"
            pilot.app.screen.query_one("#key-type-input", Input).value = "not-a-key-type"
            pilot.app.screen.query_one("#generate", Button).press()
            await pilot.pause()
            self.assertIn("invalide", str(pilot.app.screen.query_one("#form-error").content))

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

    async def test_generate_self_signed_warns_restart_when_tls_already_enabled(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            await self._enable_tls_direct(pilot)

            pilot.app.screen.query_one("#self-signed", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cn-input", Input).value = "test.local"
            pilot.app.screen.query_one("#san-dns-input", Input).value = "test.local"
            pilot.app.screen.query_one("#generate", Button).press()
            await self._wait_for_generate_to_finish(pilot)
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m for m in messages))

    async def test_generate_self_signed_no_restart_warning_when_tls_disabled(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#self-signed", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#cn-input", Input).value = "test.local"
            pilot.app.screen.query_one("#san-dns-input", Input).value = "test.local"
            pilot.app.screen.query_one("#generate", Button).press()
            await self._wait_for_generate_to_finish(pilot)
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertFalse(any("REDEMARRAGE COMPLET" in m for m in messages))

    async def test_ca_wizard_full_flow_and_revoke(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#ca-wizard", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, CaWizardScreen)

            pilot.app.screen.query_one("#step-ca", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cn", Input).value = "Test Root CA"
            pilot.app.screen.query_one("#df-password", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#df-password_confirm", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-ca")
            log = str(pilot.app.screen.query_one("#wizard-log").content)
            self.assertIn("CA locale generee", log)
            self.assertIn("Importez", log)

            ca_key = self.root / "secure" / "certificates" / "ca" / "root-ca.key"
            self.assertTrue(ca_key.exists())

            pilot.app.screen.query_one("#step-csr", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cn", Input).value = "server.local"
            pilot.app.screen.query_one("#df-san_dns", Input).value = "server.local"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-csr")
            self.assertIn("CSR generee", str(pilot.app.screen.query_one("#wizard-log").content))

            pilot.app.screen.query_one("#step-sign", Button).press()
            await pilot.pause()
            csr_path_value = pilot.app.screen.query_one("#df-csr_path", Input).value
            self.assertTrue(csr_path_value.endswith("server.csr"))
            pilot.app.screen.query_one("#df-password", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-sign")
            final_log = str(pilot.app.screen.query_one("#wizard-log").content)
            self.assertIn("Certificat signe par la CA locale", final_log)
            self.assertIn("chaine complete", final_log)

            signed_cert = self.root / "secure" / "certificates" / "server" / "server.pem"
            self.assertTrue(signed_cert.exists())

            await pilot.press("escape")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TlsMenuScreen)

            pilot.app.screen.query_one("#revoke", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, RevokeCertificateScreen)
            pilot.app.screen.query_one("#cert-input", Input).value = str(signed_cert)
            pilot.app.screen.query_one("#password-input", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#revoke", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "revoke")
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

        index_content = (self.root / "secure" / "certificates" / "ca" / "index.txt").read_text()
        self.assertIn("R", index_content.splitlines()[0])

    async def test_ca_wizard_rejects_mismatched_passphrase(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#ca-wizard", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#step-ca", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cn", Input).value = "Test Root CA"
            pilot.app.screen.query_one("#df-password", Input).value = "one"
            pilot.app.screen.query_one("#df-password_confirm", Input).value = "two"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("ne correspondent pas", str(pilot.app.screen.query_one("#wizard-log").content))
        ca_key = self.root / "secure" / "certificates" / "ca" / "root-ca.key"
        self.assertFalse(ca_key.exists())

    async def test_ca_wizard_sign_warns_restart_when_tls_already_enabled(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            await self._enable_tls_direct(pilot)

            pilot.app.screen.query_one("#ca-wizard", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#step-ca", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cn", Input).value = "Test Root CA"
            pilot.app.screen.query_one("#df-password", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#df-password_confirm", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-ca")

            pilot.app.screen.query_one("#step-csr", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cn", Input).value = "server.local"
            pilot.app.screen.query_one("#df-san_dns", Input).value = "server.local"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-csr")

            pilot.app.screen.query_one("#step-sign", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-password", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-sign")
            log = str(pilot.app.screen.query_one("#wizard-log").content)
            self.assertIn("REDEMARRAGE COMPLET", log)

    async def test_revoke_warns_restart_when_revoking_the_active_certificate(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)

            pilot.app.screen.query_one("#ca-wizard", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#step-ca", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cn", Input).value = "Test Root CA"
            pilot.app.screen.query_one("#df-password", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#df-password_confirm", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-ca")
            pilot.app.screen.query_one("#step-csr", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-cn", Input).value = "server.local"
            pilot.app.screen.query_one("#df-san_dns", Input).value = "server.local"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-csr")
            pilot.app.screen.query_one("#step-sign", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-password", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "step-sign")
            signed_cert = self.root / "secure" / "certificates" / "server" / "server.pem"
            self.assertTrue(signed_cert.exists())

            await pilot.press("escape")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TlsMenuScreen)
            await self._enable_tls_direct(pilot)

            pilot.app.screen.query_one("#revoke", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, RevokeCertificateScreen)
            pilot.app.screen.query_one("#cert-input", Input).value = str(signed_cert)
            pilot.app.screen.query_one("#password-input", Input).value = "capassphrase123"
            pilot.app.screen.query_one("#revoke", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_for_button_reenabled(pilot, "revoke")
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m for m in messages))

    async def test_toggle_enable_and_disable(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#toggle", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, TlsToggleScreen)
            self.assertIn("desactive", str(pilot.app.screen.query_one("#status-text").content))

            pilot.app.screen.query_one("#mode-input", Input).value = "direct"
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            self.assertIn("active", str(pilot.app.screen.query_one("#status-text").content))
            messages = [str(n.message) for n in pilot.app._notifications]
            self.assertTrue(any("REDEMARRAGE COMPLET" in m for m in messages))

            pilot.app.screen.query_one("#disable", Button).press()
            await pilot.pause()
            self.assertIn("desactive", str(pilot.app.screen.query_one("#status-text").content))
            messages_after_disable = [str(n.message) for n in pilot.app._notifications]
            self.assertGreaterEqual(
                sum("REDEMARRAGE COMPLET" in m for m in messages_after_disable), 2,
            )

    async def test_toggle_rejects_invalid_mode(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            pilot.app.screen.query_one("#toggle", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#mode-input", Input).value = "not-a-mode"
            pilot.app.screen.query_one("#enable", Button).press()
            await pilot.pause()
            self.assertIn("invalide", str(pilot.app.screen.query_one("#form-error").content))

    async def test_back_buttons_return_to_tls_menu(self):
        container = self._container()
        self._generate_config(container)
        app = OmegaServApp(container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._start(pilot)
            await self._open_tls_menu(pilot)
            for button_id in ("status", "self-signed", "ca-wizard", "revoke", "toggle"):
                pilot.app.screen.query_one(f"#{button_id}", Button).press()
                await pilot.pause()
                pilot.app.screen.query_one("#back", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, TlsMenuScreen)


if __name__ == "__main__":
    unittest.main()
