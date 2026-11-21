"""Tableau de bord web, lot 2 : « Configuration distante » dans l'ecran Instances (decisions de l'auteur des
2026-11-15 et 16, PROJETS §7.10-7.11) et ecran de reglage de l'administration web.

- colonne « Accès distant » (lue dans la configuration de chaque instance, lecture seule) ;
- bouton grise avec la raison tant que l'option est inactive sur l'instance choisie ;
- instance pilotee : l'ecran s'ouvre ; autre instance : confirmation avec son nom, bascule, puis ouverture ;
- l'ecran refuse un reglage invalide sans rien ecrire (saisie gardee), enregistre un reglage valide ;
- les boutons tiennent en 80x24 ;
- « Relier au maître » (2026-11-16) : maitre parmi les autres instances de cette machine dont l'administration web
  est active (l'instance courante par defaut), remplacement d'un maitre deja accepte seulement apres confirmation."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from textual.widgets import Button, DataTable, Input, Select, Static

from omega_serv.application.admin_web.manage_accounts import add_account
from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.domain.admin_web import totp
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.pending_instance_switch import OPEN_ADMIN_WEB
from omega_serv.interfaces.tui.screens.admin_accounts_screen import (
    AdminAccountsScreen,
    BackupCodesScreen,
    TotpEnrolScreen,
)
from omega_serv.interfaces.tui.screens.admin_master_screen import AdminMasterScreen
from omega_serv.interfaces.tui.screens.admin_web_screen import AdminWebScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.link_master_dialog import LinkMasterScreen
from omega_serv.ports.instance_command_port import CommandReply
from tests.integration import test_tui_instances as _instances

_entry = _instances._entry


async def _fix_button(pilot, action):
    """Bouton d'un point du bilan : monte un peu apres le texte (sous le texte depuis le 2026-11-17)."""
    for _attempt in range(40):
        found = pilot.app.screen.query(f".fix-{action}")
        if found:
            return found.first(Button)
        await pilot.pause()
    return pilot.app.screen.query_one(f".fix-{action}", Button)


def _state_text(screen) -> str:
    """Texte du bilan « prêt / ce qui manque » (lot 8)."""
    return "\n".join(str(w.render()) for w in screen.query("#admin-web-state Static"))


class _FakeSetup:
    """Machine simulee : port pris ou libre, droits poses sans sudo."""

    def __init__(self, *, taken: int | None = None, fire: str = "") -> None:
        self.taken = taken
        self.fire = fire
        self.openings: list = []

    def can_listen(self, bind, port):
        return "in_use" if port == self.taken else ""

    def machine_names(self):
        return "machine", ("127.0.0.1", "192.168.1.10")

    def active_firewall(self):
        return "ufw"

    def share_with_group(self, directories, key, certificate, group, *, privileged):
        return ""

    def linked_firewall(self, project_root):
        return self.fire

    def open_firewall_port(self, launcher, port, sources, label):
        from omega_serv.ports.admin_web_setup_port import FirewallOpening

        self.openings.append((launcher, port, sources, label))
        return FirewallOpening(True, tuple(("nftables", source, "ajoutee") for source in sources))


class _FakeTool:
    def generate_self_signed(self, params, key_path, cert_path):
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("cle")
        cert_path.write_text("certificat")


def _enable_admin_web(config_file: Path, **settings) -> None:
    data = json.loads(config_file.read_text())
    data.setdefault("options", {})["admin_web"] = {"enabled": True, **settings}
    config_file.write_text(json.dumps(data))


class _FakeCommands:
    """Repond comme la CLI des instances : identite du maitre, accept (refuse sans --replace si `exists`), add."""

    def __init__(self, *, exists: bool = False) -> None:
        self.calls: list[tuple[Path, tuple[str, ...], str]] = []
        self._exists = exists

    def run(self, root, arguments, stdin=""):
        arguments = tuple(arguments)
        self.calls.append((root, arguments, stdin))
        if arguments[:3] == ("admin-web", "instances", "identity"):
            return CommandReply(0, json.dumps({"maitre_id": "a" * 32, "nom": "maitre"}), "")
        if arguments[:3] == ("admin-web", "master", "accept"):
            if self._exists and "--replace" not in arguments:
                return CommandReply(3, "", "Un autre maître est déjà accepté (ancien) : ajoutez --replace.")
            return CommandReply(0, json.dumps({"jeton": "jeton-secret", "empreinte": "", "port": 8443}), "")
        return CommandReply(0, "Instance ajoutée.", "")


class TestTuiAdminWeb(unittest.IsolatedAsyncioTestCase):
    setUp = _instances.TestTuiInstances.setUp
    tearDown = _instances.TestTuiInstances.tearDown
    _container = _instances.TestTuiInstances._container
    _reach_home = _instances.TestTuiInstances._reach_home
    _open_instances = _instances.TestTuiInstances._open_instances
    _select_row = _instances.TestTuiInstances._select_row

    def _other_instance(self, *, admin: bool) -> Path:
        other = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        (other / ".venv" / "bin").mkdir(parents=True)
        (other / ".venv" / "bin" / "python").touch()
        (other / "config").mkdir()
        (other / "config" / "omega-serve.json").write_text(json.dumps({"server": {"bind": "127.0.0.1", "port": 8081}}))
        if admin:
            _enable_admin_web(other / "config" / "omega-serve.json", port=8444)
        return other

    def _prepared(self, *, current_admin: bool, other_admin: bool):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        if current_admin:
            _enable_admin_web(container.config_file)
        other = self._other_instance(admin=other_admin)
        container.instance_registry.save([_entry(name="prod", path=self.root), _entry(name="test", path=other,
                                                                                         port=8081)])
        return container, other

    async def test_column_and_greyed_button_with_its_reason(self):
        container, _other = self._prepared(current_admin=False, other_admin=True)
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            table = pilot.app.screen.query_one("#instances-table", DataTable)
            self.assertEqual(table.get_row_at(0)[-1], "inactif")
            self.assertEqual(table.get_row_at(1)[-1], "actif (port 8444)")
            await self._select_row(pilot, 0)
            self.assertTrue(pilot.app.screen.query_one("#remote-config", Button).disabled)
            hint = str(pilot.app.screen.query_one("#remote-config-hint", Static).render())
            self.assertIn("admin_web", hint)
            await self._select_row(pilot, 1)
            self.assertFalse(pilot.app.screen.query_one("#remote-config", Button).disabled)

    async def test_current_instance_listed_even_when_not_registered(self):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        _enable_admin_web(container.config_file)
        container.instance_registry.save([])  # instance d'origine : jamais inscrite au registre
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            table = pilot.app.screen.query_one("#instances-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertIn("(courante)", table.get_row_at(0)[0])
            self.assertEqual(table.get_row_at(0)[-1], "actif (port 9643)")
            await self._select_row(pilot, 0)
            self.assertTrue(pilot.app.screen.query_one("#uninstall-instance", Button).disabled)
            self.assertTrue(pilot.app.screen.query_one("#switch-to", Button).disabled)
            pilot.app.screen.query_one("#remote-config", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, AdminWebScreen)
        self.assertEqual(container.instance_registry.load(), [])  # l'affichage n'ecrit rien au registre

    async def test_current_instance_opens_the_screen_and_saves(self):
        container, _other = self._prepared(current_admin=True, other_admin=False)
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 0)
            pilot.app.screen.query_one("#remote-config", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            self.assertIsInstance(screen, AdminWebScreen)
            self.assertIn("http://127.0.0.1:9643/", _state_text(screen))

            screen.query_one("#port-input", Input).value = "abc"  # refuse : rien d'ecrit, saisie gardee
            screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("port", str(screen.query_one("#admin-web-error", Static).render()))
            self.assertEqual(screen.query_one("#port-input", Input).value, "abc")
            saved = load_config(container.configuration, container.config_file).config
            self.assertNotIn("port", saved.options["admin_web"].settings)

            screen.query_one("#port-input", Input).value = "9643"
            screen.query_one("#bind-input", Input).value = "192.168.1.10"  # hors boucle locale sans TLS
            screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertEqual(screen.query_one("#tls-select", Select).value, "own")  # TLS choisi tout seul
            self.assertIn("Certificat dédié", str(screen.query_one("#admin-web-error", Static).render()))
            saved = load_config(container.configuration, container.config_file).config
            self.assertEqual(saved.options["admin_web"].settings["tls"], "own")
            self.assertTrue(await _fix_button(pilot, "certificate"))  # certificat dedie absent : bouton

            screen.query_one("#bind-input", Input).value = "127.0.0.1"
            screen.query_one("#port-input", Input).value = "9443"
            screen.query_one("#tls-select", Select).value = "none"
            self.assertEqual(screen.query_one("#theme-select", Select).value, "tui")  # defaut : comme la TUI
            screen.query_one("#theme-select", Select).value = "omega-light"  # plan §9.7
            screen.query_one("#save", Button).press()
            await pilot.pause()
            saved = load_config(container.configuration, container.config_file).config
            self.assertTrue(saved.options["admin_web"].enabled)  # l'activation n'est jamais changee ici
            self.assertEqual(saved.options["admin_web"].settings["port"], 9443)
            self.assertEqual(saved.options["admin_web"].settings["theme"], "omega-light")
            self.assertIn("9443", _state_text(screen))

    async def _open_remote_config(self, pilot):
        await self._reach_home(pilot)
        await self._open_instances(pilot)
        await self._select_row(pilot, 0)
        pilot.app.screen.query_one("#remote-config", Button).press()
        for _attempt in range(40):  # ecran et cadre Etat remplis juste apres l'ouverture : attendre, sous charge
            await pilot.pause()
            if isinstance(pilot.app.screen, AdminWebScreen) and _state_text(pilot.app.screen):
                break
        self.assertIsInstance(pilot.app.screen, AdminWebScreen)
        return pilot.app.screen

    async def test_alerts_screen_saves_thresholds_and_maintenance(self):
        """Etude modules du panneau web, module 1 (2026-11-17) : alertes locales, reglees dans la TUI."""
        from omega_serv.interfaces.tui.screens.admin_alerts_screen import AdminAlertsScreen
        container, _other = self._prepared(current_admin=True, other_admin=False)
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            screen = await self._open_remote_config(pilot)
            screen.query_one("#alerts", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            self.assertIsInstance(screen, AdminAlertsScreen)
            self.assertEqual(screen.query_one("#rule-disque", Input).value, "90")  # seuils par defaut
            screen.query_one("#rule-disque", Input).value = "150"
            screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("Disque", str(screen.query_one("#alerts-error", Static).render()))  # hors bornes : rien
            self.assertNotIn("alerts", load_config(container.configuration, container.config_file)
                             .config.options["admin_web"].settings)
            screen.query_one("#rule-disque", Input).value = "80"
            screen.query_one("#rule-swap", Input).value = ""
            screen.query_one("#save", Button).press()
            await pilot.pause()
            alerts = load_config(container.configuration, container.config_file).config.options["admin_web"].settings[
                "alerts"]
            self.assertEqual((alerts["disque"], alerts["swap"], alerts["memoire"]), (80, False, 90))
            screen.query_one("#maintenance-1h", Button).press()
            await pilot.pause()
            self.assertIsNotNone(container.admin_alert_store().maintenance_until())
            self.assertIn("Maintenance jusqu", str(screen.query_one("#alerts-maintenance", Static).render()))
            screen.query_one("#maintenance-end", Button).press()
            await pilot.pause()
            self.assertIsNone(container.admin_alert_store().maintenance_until())

    async def test_sessions_screen_lists_published_sessions_and_requests_a_close(self):
        """Etude modules du panneau web, module 5 (2026-11-17) : Comptes -> Sessions."""
        import time as _time

        from omega_serv.interfaces.tui.screens.admin_sessions_screen import AdminSessionsScreen
        container, _other = self._prepared(current_admin=True, other_admin=False)
        files = container.admin_session_files()
        files.publish([{"id": "a" * 12, "compte": "kraynux", "adresse": "100.81.61.40", "mode": "tableau",
                        "ouverte": round(_time.time()), "activite": round(_time.time())}])
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._open_accounts(pilot)
            pilot.app.screen.query_one("#sessions", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            self.assertIsInstance(screen, AdminSessionsScreen)
            self.assertIn("100.81.61.40", str(screen.query_one("#sessions-text", Static).render()))
            screen.query_one("#sessions-select", Select).value = "a" * 12
            screen.query_one("#close", Button).press()
            await pilot.pause()
            self.assertEqual(files.take_close_requests(), ["a" * 12])

    async def test_readiness_enable_button_turns_the_option_on(self):
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        _enable_admin_web(container.config_file)
        data = json.loads(container.config_file.read_text())
        data["options"]["admin_web"]["enabled"] = False
        container.config_file.write_text(json.dumps(data))
        container.instance_registry.save([])
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 0)
            screen = pilot.app.screen
            # Option inactive : bouton grise dans Instances ; l'ecran s'ouvre quand meme pour l'activer.
            screen.query_one("#remote-config", Button).disabled = False
            screen.query_one("#remote-config", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            self.assertIsInstance(screen, AdminWebScreen)
            self.assertIn("inactive", _state_text(screen))
            (await _fix_button(pilot, "enable")).press()
            await pilot.pause()
            saved = load_config(container.configuration, container.config_file).config
            self.assertTrue(saved.options["admin_web"].enabled)
            await pilot.pause()
            for _attempt in range(40):  # bilan remonte apres l'action : attendre, sous charge
                if not pilot.app.screen.query(".fix-enable"):
                    break
                await pilot.pause()
            self.assertFalse(pilot.app.screen.query(".fix-enable"))

    async def test_port_taken_by_another_program_is_refused(self):
        container = self._container(admin_web_setup=_FakeSetup(taken=9700))
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        _enable_admin_web(container.config_file)
        container.instance_registry.save([])
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            screen = await self._open_remote_config(pilot)
            screen.query_one("#port-input", Input).value = "9700"
            screen.query_one("#save", Button).press()
            error = screen.query_one("#admin-web-error", Static)
            for _attempt in range(40):  # sous charge (suite complete), une seule pause ne suffit pas toujours
                await pilot.pause()
                if "9700" in str(error.render()):
                    break
            self.assertIn("9700", str(error.render()))
            saved = load_config(container.configuration, container.config_file).config
            self.assertNotIn("port", saved.options["admin_web"].settings)  # rien d'ecrit
            screen.query_one("#port-input", Input).value = "9701"
            screen.query_one("#save", Button).press()
            for _attempt in range(40):
                await pilot.pause()
                saved = load_config(container.configuration, container.config_file).config
                if saved.options["admin_web"].settings.get("port") == 9701:
                    break
            self.assertEqual(saved.options["admin_web"].settings["port"], 9701)

    async def test_certificate_button_generates_it(self):
        container = self._container(admin_web_setup=_FakeSetup(), certificate_tool_factory=_FakeTool)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        _enable_admin_web(container.config_file, bind="0.0.0.0", tls="own")
        container.instance_registry.save([])
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            screen = await self._open_remote_config(pilot)
            text = _state_text(screen)
            self.assertIn("https://192.168.1.10:9643/", text)
            self.assertIn("ufw", text)  # pare-feu signale
            (await _fix_button(pilot, "certificate")).press()
            await pilot.pause()
            await pilot.pause()
            self.assertTrue((self.root / "secure/certificates/admin/admin.pem").is_file())
            for _attempt in range(40):  # bilan remonte apres l'action : attendre, sous charge
                if not pilot.app.screen.query(".fix-certificate"):
                    break
                await pilot.pause()
            self.assertFalse(pilot.app.screen.query(".fix-certificate"))
            self.assertIn("Certificat présent", _state_text(screen))

    async def test_firewall_button_opens_the_port_through_linked_omega_fire(self):
        """Sous-lot 8b : omega-fire et l'instance inscrits dans la zone omega-connect -> « Ouvrir le port » appelle
        omega-fire pour les reseaux permis (boucle locale exclue), puis le bilan dit « ouvert »."""
        setup = _FakeSetup(fire="/opt/omega-fire/omega-fire.sh")
        container = self._container(admin_web_setup=setup, certificate_tool_factory=_FakeTool)
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        _enable_admin_web(container.config_file, bind="0.0.0.0", tls="own")
        container.instance_registry.save([])
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            screen = await self._open_remote_config(pilot)
            self.assertIn("omega-fire, relié par omega-connect", _state_text(screen))
            (await _fix_button(pilot, "firewall")).press()
            await pilot.pause()
            await pilot.pause()
            launcher, port, sources, label = setup.openings[0]
            self.assertEqual((launcher, port, label), ("/opt/omega-fire/omega-fire.sh", 9643,
                                                       f"omega-serv:{self.root.name}"))
            self.assertNotIn("127.0.0.0/8", sources)
            self.assertIn("192.168.0.0/16", sources)
            for _attempt in range(40):  # bilan remonte apres l'action : attendre, sous charge
                if not pilot.app.screen.query(".fix-firewall"):
                    break
                await pilot.pause()
            self.assertFalse(pilot.app.screen.query(".fix-firewall"))
            self.assertIn("ouvert par omega-fire", _state_text(screen))
            self.assertTrue((self.root / "var/lib/admin/pare-feu.json").is_file())

    async def test_other_instance_asks_then_switches_and_opens_after(self):
        container, other = self._prepared(current_admin=False, other_admin=True)
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            pilot.app.screen.query_one("#remote-config", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            texts = "\n".join(str(w.render()) for w in pilot.app.screen.query(Static))
            self.assertIn("'test'", texts)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            pending = pilot.app.pending_switch
            self.assertIsNotNone(pending)
            self.assertEqual(pending.open_after, OPEN_ADMIN_WEB)
            self.assertEqual(pending.python_executable, other / ".venv" / "bin" / "python")

    async def test_buttons_fit_in_80x24(self):
        container, _other = self._prepared(current_admin=True, other_admin=True)
        async with OmegaServApp(container).run_test(size=(80, 24)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            screen_region = pilot.app.screen.region
            for button_id in ("refresh", "create", "switch-to", "remote-config", "uninstall-instance", "back"):
                region = pilot.app.screen.query_one(f"#{button_id}", Button).region
                self.assertTrue(screen_region.contains_region(region) and region.width > 0, button_id)


    async def _open_accounts(self, pilot):
        await self._reach_home(pilot)
        await self._open_instances(pilot)
        await self._select_row(pilot, 0)
        pilot.app.screen.query_one("#remote-config", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#accounts", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, AdminAccountsScreen)

    async def test_role_is_chosen_in_a_dropdown_starting_from_the_current_role(self):
        """Essai de l'auteur du 2026-11-17 : le role se choisit dans un menu deroulant (lecture, administration)."""
        container, _other = self._prepared(current_admin=True, other_admin=False)
        add_account(container.admin_accounts, "kraynux", "un-mot-de-passe", "lecture")
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._open_accounts(pilot)
            table = pilot.app.screen.query_one("#accounts-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#role", Button).press()
            await pilot.pause()
            choice = pilot.app.screen.query_one("#df-role", Select)
            self.assertEqual(choice.value, "lecture")  # part du role actuel
            self.assertEqual([value for _label, value in choice._options], ["lecture", "administration"])
            choice.value = "administration"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            (account,) = container.admin_accounts.load()
            self.assertEqual(account.role, "administration")

    async def test_accounts_add_refuse_then_totp(self):
        container, _other = self._prepared(current_admin=True, other_admin=False)
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._open_accounts(pilot)
            pilot.app.screen.query_one("#add", Button).press()
            await pilot.pause()
            form = pilot.app.screen
            form.query_one("#df-username", Input).value = "admin"
            form.query_one("#df-password", Input).value = "court"
            form.query_one("#df-password2", Input).value = "court"
            form.query_one("#df-role", Select).value = "administration"
            form.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(container.admin_accounts.load(), ())  # mot de passe trop court : rien d'ecrit
            form = pilot.app.screen
            form.query_one("#df-password", Input).value = "un-mot-de-passe"
            form.query_one("#df-password2", Input).value = "un-mot-de-passe"
            form.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, AdminAccountsScreen)
            (account,) = container.admin_accounts.load()
            self.assertEqual((account.username, account.role, account.totp_enabled), ("admin", "administration", False))

            table = pilot.app.screen.query_one("#accounts-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#totp-enable", Button).press()
            await pilot.pause()
            enrol = pilot.app.screen
            self.assertIsInstance(enrol, TotpEnrolScreen)
            secret = str(enrol.query_one("#totp-secret", Static).render()).replace(" ", "")
            self.assertIn("otpauth://totp/", str(enrol.query_one("#totp-uri", Static).render()))
            self.assertIn("█", str(enrol.query_one("#totp-qr", Static).render()))
            enrol.query_one("#totp-code", Input).value = "000000"
            enrol.query_one("#confirm-code", Button).press()
            await pilot.pause()
            self.assertFalse(container.admin_accounts.load()[0].totp_enabled)
            enrol.query_one("#totp-code", Input).value = totp.code_at(secret, totp.step_of(time.time()))
            enrol.query_one("#confirm-code", Button).press()
            await pilot.pause()
            self.assertTrue(container.admin_accounts.load()[0].totp_enabled)
            shown = str(enrol.query_one("#totp-result", Static).render())
            self.assertEqual(len(re.findall(r"\b[A-Z2-9]{4}-[A-Z2-9]{4}\b", shown)), 10)  # codes de secours
            await pilot.press("escape")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, AdminAccountsScreen)
            table = pilot.app.screen.query_one("#accounts-table", DataTable)
            self.assertEqual(table.get_row_at(0)[-1], "10 sur 10")
            table.move_cursor(row=0)
            await pilot.pause()
            pilot.app.screen.query_one("#backup-codes", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, BackupCodesScreen)
            listed = str(pilot.app.screen.query_one("#backup-codes-list", Static).render())
            self.assertEqual(len(re.findall(r"\b[A-Z2-9]{4}-[A-Z2-9]{4}\b", listed)), 10)

    async def test_accounts_buttons_fit_in_80x24(self):
        container, _other = self._prepared(current_admin=True, other_admin=False)
        async with OmegaServApp(container).run_test(size=(80, 24)) as pilot:
            await self._open_accounts(pilot)
            screen_region = pilot.app.screen.region
            for button_id in ("add", "password", "role", "totp-enable", "totp-disable", "backup-codes", "remove", "back"):
                region = pilot.app.screen.query_one(f"#{button_id}", Button).region
                self.assertTrue(screen_region.contains_region(region) and region.width > 0, button_id)

    # ------------------------------------------------------------------ lot 6 : maitre accepte
    async def _open_master(self, pilot):
        await self._reach_home(pilot)
        await self._open_instances(pilot)
        await self._select_row(pilot, 0)
        pilot.app.screen.query_one("#remote-config", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#master", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, AdminMasterScreen)

    async def test_master_pairing_window_replace_confirmation_and_revoke(self):
        container, _other = self._prepared(current_admin=True, other_admin=False)
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._open_master(pilot)
            screen = pilot.app.screen
            self.assertTrue(screen.query_one("#revoke", Button).disabled)
            self.assertTrue(screen.query_one("#close-pairing", Button).disabled)
            screen.query_one("#rights-select", Select).value = "administration"
            await pilot.pause()
            screen.query_one("#open-pairing", Button).press()
            await pilot.pause()
            shown = str(screen.query_one("#pairing-state", Static).render())
            code = re.search(r"\b[A-Z2-9]{4}-[A-Z2-9]{4}\b", shown).group(0)
            window = container.admin_master_manager().pairing()
            self.assertEqual((code.replace("-", ""), window.rights), (window.code, "administration"))
            self.assertFalse(screen.query_one("#close-pairing", Button).disabled)
            screen.query_one("#close-pairing", Button).press()
            await pilot.pause()
            self.assertIsNone(container.admin_master_manager().pairing())

            container.admin_master_manager().accept("1" * 32, "maitre A", "lecture", replace_existing=False,
                                                    source="test")
            await pilot.pause(1.2)  # rafraichi chaque seconde
            self.assertIn("maitre A", str(screen.query_one("#master-state", Static).render()))
            screen.query_one("#open-pairing", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)  # remplacer demande confirmation
            pilot.app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            self.assertIsNone(container.admin_master_manager().pairing())
            screen.query_one("#revoke", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIsNone(container.admin_master_manager().master())
            audit = (self.root / "var" / "log" / "admin-audit.log").read_text()
            self.assertIn("maitre revoque nom='maitre A'", audit)

    async def test_remote_config_buttons_fit_in_80x24(self):
        container, _other = self._prepared(current_admin=True, other_admin=False)
        async with OmegaServApp(container).run_test(size=(80, 24)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 0)
            pilot.app.screen.query_one("#remote-config", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, AdminWebScreen)
            screen_region = pilot.app.screen.region
            for button_id in ("save", "accounts", "master", "back"):
                region = pilot.app.screen.query_one(f"#{button_id}", Button).region
                self.assertTrue(screen_region.contains_region(region) and region.width > 0, button_id)

    async def test_master_buttons_fit_in_80x24(self):
        container, _other = self._prepared(current_admin=True, other_admin=False)
        container.admin_master_manager().accept("1" * 32, "maitre", "lecture", replace_existing=False, source="t")
        async with OmegaServApp(container).run_test(size=(80, 24)) as pilot:
            await self._open_master(pilot)
            screen_region = pilot.app.screen.region
            for button_id in ("open-pairing", "close-pairing", "revoke", "back"):
                region = pilot.app.screen.query_one(f"#{button_id}", Button).region
                self.assertTrue(screen_region.contains_region(region) and region.width > 0, button_id)

    async def test_history_can_be_turned_off_and_back_on(self):
        """Lot 7 : choix « Historique » de l'écran Configuration distante, écrit dans options.admin_web.history."""
        container, _other = self._prepared(current_admin=True, other_admin=False)
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 0)
            pilot.app.screen.query_one("#remote-config", Button).press()
            await pilot.pause()
            screen = pilot.app.screen
            self.assertEqual(screen.query_one("#history-select", Select).value, "on")
            screen.query_one("#history-select", Select).value = "off"
            screen.query_one("#save", Button).press()
            await pilot.pause()
            option = load_config(container.configuration, container.config_file).config.options["admin_web"]
            self.assertIs(option.settings["history"], False)
            screen.query_one("#history-select", Select).value = "on"
            screen.query_one("#save", Button).press()
            await pilot.pause()
            option = load_config(container.configuration, container.config_file).config.options["admin_web"]
            self.assertIs(option.settings["history"], True)

    async def test_totp_secret_and_link_can_be_copied(self):
        """Retour de l'auteur (2026-11-17) : sans scanner le QR code, le secret ou le lien doivent se coller dans
        l'application ; personne ne peut les retenir. Les boutons tiennent en 80x24."""
        container, _other = self._prepared(current_admin=True, other_admin=False)
        copied: list[str] = []

        class _Clipboard:
            def copy(self, text):
                copied.append(text)
                return "xclip"

        container._clipboard = _Clipboard()
        async with OmegaServApp(container).run_test(size=(80, 24)) as pilot:
            await self._reach_home(pilot)
            pilot.app.push_screen(TotpEnrolScreen(container=container, username="admin"))
            await pilot.pause()
            screen = pilot.app.screen
            secret = str(screen.query_one("#totp-secret", Static).render()).replace(" ", "")
            for button_id in ("confirm-code", "copy-secret", "copy-uri", "back"):
                region = screen.query_one(f"#{button_id}", Button).region
                self.assertTrue(screen.region.contains_region(region) and region.width > 0, button_id)
            screen.query_one("#copy-secret", Button).press()
            await pilot.pause()
            screen.query_one("#copy-uri", Button).press()
            await pilot.pause()
        self.assertEqual(copied[0], secret)
        self.assertTrue(copied[1].startswith("otpauth://totp/") and f"secret={secret}" in copied[1])

    async def test_instances_buttons_fit_in_80x24(self):
        container, _other = self._prepared(current_admin=True, other_admin=True)
        async with OmegaServApp(container).run_test(size=(80, 24)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            screen_region = pilot.app.screen.region
            for button_id in ("refresh", "create", "uninstall-instance", "switch-to", "remote-config", "link-master",
                              "back"):
                region = pilot.app.screen.query_one(f"#{button_id}", Button).region
                self.assertTrue(screen_region.contains_region(region) and region.width > 0, button_id)

    async def _link_from_row(self, pilot, row: int) -> LinkMasterScreen:
        await self._reach_home(pilot)
        await self._open_instances(pilot)
        await self._select_row(pilot, row)
        self.assertFalse(pilot.app.screen.query_one("#link-master", Button).disabled)
        pilot.app.screen.query_one("#link-master", Button).press()
        await pilot.pause()
        dialog = pilot.app.screen
        self.assertIsInstance(dialog, LinkMasterScreen)
        return dialog

    async def _wait_calls(self, pilot, commands: _FakeCommands, count: int) -> None:
        for _ in range(100):
            await pilot.pause()
            if len(commands.calls) >= count:
                return
            await asyncio.sleep(0.02)
        self.fail(f"commandes attendues : {count}, lancees : {commands.calls}")

    async def test_link_master_defaults_to_the_current_instance(self):
        container, other = self._prepared(current_admin=True, other_admin=True)
        commands = _FakeCommands()
        container._instance_commands = commands
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            dialog = await self._link_from_row(pilot, 1)  # « test » suivie par l'instance courante
            self.assertEqual(dialog.query_one("#link-master", Select).value, str(self.root))
            dialog.query_one("#link-rights", Select).value = "administration"
            dialog.query_one("#link", Button).press()
            await self._wait_calls(pilot, commands, 3)
        (master_root, identity, _s), (follower_root, accept, _s2), (add_root, add, stdin) = commands.calls
        self.assertEqual((master_root, follower_root, add_root), (self.root, other, self.root))
        self.assertEqual(identity, ("admin-web", "instances", "identity"))
        self.assertIn("administration", accept)
        self.assertNotIn("--replace", accept)
        self.assertEqual(add[:6], ("admin-web", "instances", "add", "127.0.0.1", "8444", "--fingerprint"))
        self.assertNotIn("jeton-secret", add)  # jamais sur la ligne de commande
        self.assertEqual(stdin, "jeton-secret\n")

    async def test_link_master_replaces_only_after_confirmation(self):
        container, _other = self._prepared(current_admin=True, other_admin=True)
        commands = _FakeCommands(exists=True)
        container._instance_commands = commands
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            dialog = await self._link_from_row(pilot, 1)
            dialog.query_one("#link", Button).press()
            await self._wait_calls(pilot, commands, 2)
            for _ in range(50):
                await pilot.pause()
                if isinstance(pilot.app.screen, ConfirmScreen):
                    break
                await asyncio.sleep(0.02)
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertEqual(len(commands.calls), 2)  # rien d'ajoute chez le maitre avant la confirmation
            pilot.app.screen.query_one("#confirm", Button).press()
            await self._wait_calls(pilot, commands, 5)
        self.assertIn("--replace", commands.calls[3][1])
        self.assertEqual(commands.calls[4][1][:3], ("admin-web", "instances", "add"))

    async def test_link_master_greyed_when_the_chosen_instance_has_no_admin_web(self):
        """Retour de l'auteur (2026-11-17) : une seule instance, hors registre, admin_web inactif -> le bouton était
        actif et un clic ne faisait rien. Il est grisé, la raison « admin_web » s'affiche."""
        container = self._container()
        generate_default_config(container.configuration, container.filesystem, container.config_file)
        container.instance_registry.save([])
        container._instance_commands = _FakeCommands()
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 0)
            self.assertTrue(pilot.app.screen.query_one("#link-master", Button).disabled)
            self.assertIn("admin_web", str(pilot.app.screen.query_one("#remote-config-hint", Static).render()))
        self.assertEqual(container._instance_commands.calls, [])

    async def test_link_master_greyed_without_another_admin_instance(self):
        container, _other = self._prepared(current_admin=False, other_admin=True)
        container._instance_commands = _FakeCommands()
        async with OmegaServApp(container).run_test(size=(140, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_instances(pilot)
            await self._select_row(pilot, 1)
            self.assertTrue(pilot.app.screen.query_one("#link-master", Button).disabled)
            hint = str(pilot.app.screen.query_one("#remote-config-hint", Static).render())
            self.assertIn("administration web active", hint)


if __name__ == "__main__":
    unittest.main()
