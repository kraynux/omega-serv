"""RIPOSTE lot 5 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §5, topo §6) : ecran ACTIVE SECURITE a trois colonnes et
les 6 ecrans RIPOSTE, sur une vraie base dans un projet temporaire (jamais le var/ du depot). Les ecrans ne
touchent jamais au registre : on verifie les COMMANDES deposees (le processus RIPOSTE n'est pas lance ici,
il est couvert par test_riposte_process_actions.py) et la configuration reellement ecrite."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textual.widgets import Button, DataTable, Input, Select, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.riposte.run_riposte import STATE_HEARTBEAT, STATE_PID
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.riposte.actions import RiposteAction
from omega_serv.domain.security.riposte.history import Episode, PastAction, SourceHistory
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.infrastructure.riposte.journal_events import read_journal_events
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.active_defense_menu_screen import ActiveDefenseMenuScreen
from omega_serv.interfaces.tui.screens.choice_screen import ChoiceScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.riposte_actions_screen import RiposteActionsScreen
from omega_serv.interfaces.tui.screens.riposte_policies_screen import RipostePoliciesScreen
from omega_serv.interfaces.tui.screens.riposte_policy_form_screen import RipostePolicyFormScreen
from omega_serv.interfaces.tui.screens.riposte_recidives_screen import RiposteRecidivesScreen
from omega_serv.interfaces.tui.screens.riposte_settings_screen import RiposteSettingsScreen
from omega_serv.interfaces.tui.screens.riposte_simulate_screen import RiposteSimulateScreen
from omega_serv.interfaces.tui.screens.riposte_status_screen import RiposteStatusScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]
IP = "203.0.113.7"
SCAN = {"id": "scan", "name": "Scan", "when": {"attack_classes": ["scan"], "returns": 3, "within_seconds": 604800},
        "then": {"action": "local_ban"}}


def _open_store(path: Path, write: bool) -> SqliteRiposteStore:
    return SqliteRiposteStore(open_riposte_connection(path, read_only=not write, create=False))


class TestTuiRiposte(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(
            project_root=self.root,
            riposte_store_factory=_open_store,
            riposte_journal_reader=read_journal_events,
            instance_registry_path=self.root.parent / f"{self.root.name}-instances.json",
        )
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)
        self.database = self.root / "var" / "lib" / "riposte.sqlite3"
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self._tmp.cleanup()

    # --- Aides ----------------------------------------------------------------------------------

    def _config(self):
        result = load_config(self.container.configuration, self.container.config_file)
        assert result.success and result.config is not None
        return result.config

    def _set_options(self, *, riposte_enabled=True, policies=(SCAN,), waf=True):
        config = self._config()
        options = dict(config.options)
        options["riposte"] = Option(name="riposte", enabled=riposte_enabled, settings={"policies": list(policies)})
        options["waf"] = Option(name="waf", enabled=waf, settings=dict(options["waf"].settings) if "waf" in options else {})
        self.container.configuration.save(self.container.config_file, replace(config, options=options))

    def _riposte_settings(self):
        return self._config().options["riposte"].settings

    def _create_database(self) -> SqliteRiposteStore:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        return SqliteRiposteStore(open_riposte_connection(self.database))  # comme le processus

    def _seed_action(self, store, **changes) -> RiposteAction:
        action = RiposteAction(
            id="a1b2c3d4e5f6", ip=IP, kind="local_ban", policy_id="scan", created_at=self.now - timedelta(minutes=5),
            ends_at=self.now + timedelta(hours=1), state="applied", tier_index=0, event_id="waf:r1",
        )
        action = replace(action, **changes)
        store.save_action(action)
        return action

    def _pending(self):
        store = _open_store(self.database, False)
        try:
            return [(c.kind, c.params) for c in store.pending_commands(20)]
        finally:
            store.close()

    async def _menu(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)
        pilot.app.screen.query_one("#active-defense", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ActiveDefenseMenuScreen)

    async def _open(self, pilot, item_id, screen_class):
        await self._menu(pilot)
        pilot.app.screen.query_one(f"#{item_id}", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, screen_class)
        return pilot.app.screen

    async def _press(self, pilot, selector):
        pilot.app.screen.query_one(selector, Button).press()
        await pilot.pause()

    async def _choose(self, pilot, choice, *, check=False):
        self.assertIsInstance(pilot.app.screen, ChoiceScreen)
        if check:
            pilot.app.screen.query_one("#choice-checkbox").value = True
        await self._press(pilot, f"#choice-{choice}")

    async def _select_row(self, pilot, table_id, row=0):
        table = pilot.app.screen.query_one(table_id, DataTable)
        table.focus()
        table.move_cursor(row=row)
        await pilot.press("enter")
        await pilot.pause()

    async def _wait_workers(self, pilot):
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

    # --- Menu -------------------------------------------------------------------------------------

    async def test_menu_has_three_columns_in_order_and_fits_80_columns(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(80, 30)) as pilot:
            await self._menu(pilot)
            menus = list(pilot.app.screen.query(".omega-security-menu"))
            self.assertEqual([str(m.border_title) for m in menus], ["WAF", "ACTIVE DEFENSE", "RIPOSTE"])
            self.assertLessEqual(max(m.region.right for m in menus), 80)
            self.assertEqual(menus[0].region.y, menus[2].region.y)
            self.assertEqual(str(pilot.app.screen.query_one("#waf-rate-limit", Button).label), "Limitations")
            for item_id in ("riposte-status", "riposte-policies", "riposte-actions", "riposte-recidives",
                            "riposte-simulate", "riposte-settings"):
                self.assertGreater(pilot.app.screen.query_one(f"#{item_id}", Button).region.width, 10)

    async def test_every_riposte_screen_opens_without_database_and_comes_back(self):
        self._set_options()
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._menu(pilot)
            for item_id, screen_class in (
                ("riposte-status", RiposteStatusScreen), ("riposte-policies", RipostePoliciesScreen),
                ("riposte-actions", RiposteActionsScreen), ("riposte-recidives", RiposteRecidivesScreen),
                ("riposte-simulate", RiposteSimulateScreen), ("riposte-settings", RiposteSettingsScreen),
            ):
                await self._press(pilot, f"#{item_id}")
                self.assertIsInstance(pilot.app.screen, screen_class)
                await self._press(pilot, "#back")
                self.assertIsInstance(pilot.app.screen, ActiveDefenseMenuScreen)
        self.assertFalse(self.database.exists())  # jamais creee par l'interface

    # --- Etat et arret d'urgence -----------------------------------------------------------------

    async def test_status_without_database_then_emergency_stop_and_resume(self):
        self._set_options()
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-status", RiposteStatusScreen)
            self.assertIn("jamais été lancé", str(screen.query_one("#riposte-status-body", Static).content))
            self.assertIn("Module : activé", str(screen.query_one("#riposte-module", Static).content))
        store = self._create_database()
        store.set_state(STATE_HEARTBEAT, datetime.now(timezone.utc).isoformat())
        store.set_state(STATE_PID, "4242")
        self._seed_action(store)
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-status", RiposteStatusScreen)
            body = str(screen.query_one("#riposte-status-body", Static).content)
            self.assertIn("actif (PID 4242)", body)
            self.assertIn("Actions en cours : 1", body)
            await self._press(pilot, "#emergency-stop")
            self.assertIn("Actions en cours : 1", str(pilot.app.screen.query_one(".omega-choice-message", Static).content))
            await self._choose(pilot, "revoke")
            await self._wait_workers(pilot)
            self.assertEqual(store.get_state("emergency_stop"), "1")
            self.assertEqual(self._pending(), [("revoke_all", {})])
            self.assertEqual(str(screen.query_one("#emergency-stop", Button).label), "Reprendre")
            await self._press(pilot, "#emergency-stop")
            self.assertEqual(store.get_state("emergency_stop"), "0")
            self.assertEqual(str(screen.query_one("#emergency-stop", Button).label), "Arrêt d'urgence")
        store.close()

    async def test_emergency_stop_only_deposits_nothing(self):
        self._set_options()
        store = self._create_database()
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "riposte-status", RiposteStatusScreen)
            await self._press(pilot, "#emergency-stop")
            await self._choose(pilot, "stop")
            self.assertEqual(store.get_state("emergency_stop"), "1")
            self.assertEqual(self._pending(), [])
        store.close()

    # --- Actions ------------------------------------------------------------------------------------

    async def test_actions_lists_in_progress_and_revoke_with_exemption_deposits_a_command(self):
        self._set_options()
        store = self._create_database()
        self._seed_action(store)
        self._seed_action(store, id="ffffffffffff", state="revoked", finished_at=self.now, finished_by="user")
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-actions", RiposteActionsScreen)
            table = screen.query_one("#actions-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(str(screen.query_one("#filter-finished", Button).label), "Terminées (1)")
            await self._select_row(pilot, "#actions-table")
            self.assertIn("a1b2c3d4e5f6", str(screen.query_one("#action-detail", Static).content))
            self.assertFalse(screen.query_one("#revoke", Button).disabled)
            await self._press(pilot, "#revoke")
            await self._choose(pilot, "exempt", check=True)
            await self._choose(pilot, "7d")
            await self._wait_workers(pilot)
            self.assertEqual(self._pending(), [("revoke", {"action_id": "a1b2c3d4e5f6", "exempt": "7d",
                                                           "not_recidive": True})])
            await self._press(pilot, "#filter-finished")
            self.assertEqual(table.row_count, 1)
            await self._select_row(pilot, "#actions-table")
            self.assertTrue(screen.query_one("#revoke", Button).disabled)  # deja terminee
            self.assertIn("levée par l'utilisateur", str(screen.query_one("#action-detail", Static).content))
        store.close()

    # --- Recidives ----------------------------------------------------------------------------------

    async def test_recidives_shows_chronology_and_forget_deposits_a_command(self):
        self._set_options()
        store = self._create_database()
        start = self.now - timedelta(days=2)
        store.save_source(SourceHistory(
            IP, episodes=(Episode(started_at=start, last_seen_at=start, attacks=4, attack_classes=("scan",)),),
            actions=(PastAction(taken_at=start, ends_at=start + timedelta(hours=1), policy_id="scan", tier_index=0),),
        ), self.now)
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-recidives", RiposteRecidivesScreen)
            self.assertEqual(screen.query_one("#sources-table", DataTable).row_count, 1)
            await self._select_row(pilot, "#sources-table")
            detail = str(screen.query_one("#source-detail", Static).content)
            self.assertIn("4 attaque(s) [scan]", detail)
            self.assertIn("Action scan palier 1", detail)
            await self._press(pilot, "#forget")
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            await self._press(pilot, "#confirm")
            await self._wait_workers(pilot)
            self.assertEqual(self._pending(), [("forget_source", {"ip": IP})])
            self.assertTrue(screen.query_one("#show-actions", Button).disabled)  # liste rafraichie, selection effacee
            await self._select_row(pilot, "#sources-table")
            await self._press(pilot, "#show-actions")
            self.assertIsInstance(pilot.app.screen, RiposteActionsScreen)
        store.close()

    # --- Simuler ------------------------------------------------------------------------------------

    async def test_simulate_explains_the_decision_with_the_real_config(self):
        self._set_options()
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-simulate", RiposteSimulateScreen)
            screen.query_one("#sim-returns", Input).value = "3"
            await self._press(pilot, "#simulate")
            result = str(screen.query_one("#simulate-result", Static).content)
            self.assertIn("action décidée", result)
            self.assertIn("Politique retenue : scan", result)
            screen.query_one("#sim-returns", Input).value = "x"
            await self._press(pilot, "#simulate")
            self.assertIn("Nombre invalide", str(screen.query_one("#simulate-result", Static).content))

    # --- Reglages -----------------------------------------------------------------------------------

    async def test_settings_saves_valid_values_and_refuses_invalid_ones(self):
        self._set_options()
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-settings", RiposteSettingsScreen)
            self.assertEqual(screen.query_one("#tiers-input", Input).value, "1h, 6h, 1d, 7d")
            screen.query_one("#tiers-input", Input).value = "2h, 12h"
            screen.query_one("#exemptions-input", Input).value = "192.0.2.0/24"
            await self._press(pilot, "#save")
            settings = self._riposte_settings()
            self.assertEqual(settings["tiers_seconds"], [7200, 43200])
            self.assertEqual(settings["exemptions"], ["192.0.2.0/24"])
            self.assertEqual(settings["policies"][0]["id"], "scan")  # politiques intactes
            screen.query_one("#tiers-input", Input).value = "2h, 30d"  # > 7 j : refuse globalement
            await self._press(pilot, "#save")
            self.assertIn("Non enregistré", str(screen.query_one("#settings-error", Static).content))
            screen.query_one("#episode-gap-input", Input).value = "abc"
            await self._press(pilot, "#save")
            self.assertIn("Durée invalide", str(screen.query_one("#settings-error", Static).content))
            self.assertEqual(self._riposte_settings()["tiers_seconds"], [7200, 43200])

    # --- Politiques et formulaire --------------------------------------------------------------

    async def test_add_a_scenario_measure_and_activate(self):
        self._set_options(policies=())
        log = self.root / "var" / "log" / "waf-alerts.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({
            "timestamp": (self.now - timedelta(hours=10 - 2 * i)).isoformat(), "request_id": f"r{i}",
            "remote_ip": IP, "action": "block", "stage": "inspection", "score": 9, "rules": ["S"],
            "findings": [{"id": "S", "pack": "sensitive-paths"}],
        }) for i in range(3)]
        log.write_text("\n".join(lines) + "\n")
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "riposte-policies", RipostePoliciesScreen)
            await self._press(pilot, "#add")
            await self._choose(pilot, "scenario")
            await self._choose(pilot, "scan-recidive")
            form = pilot.app.screen
            self.assertIsInstance(form, RipostePolicyFormScreen)
            self.assertEqual(form.query_one("#policy-id", Input).value, "scan-recidive")
            await self._press(pilot, "#measure")
            await self._wait_workers(pilot)
            measured = str(form.query_one("#measure-result", Static).content)
            self.assertIn("Aurait pris 1 action(s) sur 1 source(s)", measured)
            await self._press(pilot, "#save")
            self.assertIn("Aurait pris 1 action(s)", str(pilot.app.screen.query_one(".omega-choice-message", Static).content))
            await self._choose(pilot, "activate")
            await self._wait_workers(pilot)
            self.assertIsInstance(pilot.app.screen, RipostePoliciesScreen)
            [policy] = self._riposte_settings()["policies"]
            self.assertEqual((policy["id"], policy["enabled"], policy["origin"]),
                             ("scan-recidive", True, "scenario:scan-recidive"))
            self.assertEqual(pilot.app.screen.query_one("#policies-table", DataTable).row_count, 1)

    async def test_risky_policy_needs_a_named_confirmation_and_save_without_activating(self):
        self._set_options(policies=())
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "riposte-policies", RipostePoliciesScreen)
            await self._press(pilot, "#add")
            await self._choose(pilot, "custom")
            form = pilot.app.screen
            form.query_one("#policy-id", Input).value = "longue"
            form.query_one("#policy-name", Input).value = "Longue"
            form.query_one("#policy-tiers", Input).value = "1d, 30d"
            await self._press(pilot, "#save")
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)  # « moins prudent que la norme »
            await self._press(pilot, "#confirm")
            self.assertIn("non mesurée", str(pilot.app.screen.query_one(".omega-choice-message", Static).content))
            await self._choose(pilot, "save")
            await self._wait_workers(pilot)
            [policy] = self._riposte_settings()["policies"]
            self.assertEqual(policy["confirmed_risks"], ["long_duration"])
            self.assertFalse(policy["enabled"])
            self.assertEqual(policy["then"]["tiers_seconds"], [86400, 2592000])

    async def test_decoy_without_profile_is_read_as_no_profile(self):
        """Liste des profils laissee vide : Textual 8 renvoie Select.NULL (Select.BLANK vaut False) ; jamais
        le texte « Select.NULL » comme nom de profil (corrige le 2026-11-06)."""
        self._set_options(policies=())
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "riposte-policies", RipostePoliciesScreen)
            await self._press(pilot, "#add")
            await self._choose(pilot, "custom")
            form = pilot.app.screen
            form.query_one("#policy-id", Input).value = "leurre"
            form.query_one("#policy-name", Input).value = "Leurre"
            form.query_one("#policy-action", Select).value = "decoy"
            self.assertIs(form.query_one("#policy-decoy-profile", Select).value, Select.NULL)
            policy = form._read()
            self.assertNotIsInstance(policy, str)
            self.assertIsNone(policy.decoy_profile)

    async def test_invalid_form_writes_nothing(self):
        self._set_options(policies=())
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._open(pilot, "riposte-policies", RipostePoliciesScreen)
            await self._press(pilot, "#add")
            await self._choose(pilot, "custom")
            form = pilot.app.screen
            form.query_one("#policy-id", Input).value = "Pas Valide"
            form.query_one("#policy-name", Input).value = "x"
            await self._press(pilot, "#save")
            self.assertIn("identifiant invalide", str(form.query_one("#form-error", Static).content))
            form.query_one("#policy-returns", Input).value = "-1"
            await self._press(pilot, "#save")
            self.assertIn("Nombre invalide", str(form.query_one("#form-error", Static).content))
            self.assertEqual(self._riposte_settings()["policies"], [])

    async def test_disable_with_revoke_then_enable_and_remove(self):
        self._set_options()
        store = self._create_database()
        self._seed_action(store)
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-policies", RipostePoliciesScreen)
            await self._select_row(pilot, "#policies-table")
            await self._press(pilot, "#toggle")
            self.assertIn("Actions en cours de cette règle : 1",
                          str(pilot.app.screen.query_one(".omega-choice-message", Static).content))
            await self._choose(pilot, "revoke")
            await self._wait_workers(pilot)
            self.assertFalse(self._riposte_settings()["policies"][0]["enabled"])
            self.assertEqual([k for k, _p in self._pending()], ["reload", "revoke_policy"])
            self.assertIn("désactivée", str(screen.query_one("#policies-table", DataTable).get_row_at(0)[0]))
            await self._select_row(pilot, "#policies-table")
            self.assertEqual(str(screen.query_one("#toggle", Button).label), "Activer")
            await self._press(pilot, "#toggle")
            await self._wait_workers(pilot)
            await self._choose(pilot, "activate")
            await self._wait_workers(pilot)
            self.assertTrue(self._riposte_settings()["policies"][0]["enabled"])
            await self._select_row(pilot, "#policies-table")
            await self._press(pilot, "#remove")
            await self._press(pilot, "#confirm")
            await self._wait_workers(pilot)
            self.assertEqual(self._riposte_settings()["policies"], [])
            self.assertEqual(screen.query_one("#policies-table", DataTable).row_count, 0)
        store.close()

    async def test_network_ban_says_which_jails_and_what_a_revoke_does_not_lift(self):
        """Lot 6 : jails de l'instance installees ou absentes, jail Active Defense redondante, levee = local seul."""
        network = dict(SCAN, then={"action": "local_and_network_ban"})
        self._set_options(policies=(network,))
        installed = {"jails": frozenset({"omega-serv-riposte-1h", "omega-serv-active-defense"})}
        self.container = DependencyContainer(
            project_root=self.root, riposte_store_factory=_open_store, riposte_journal_reader=read_journal_events,
            installed_jails_reader=lambda: installed["jails"],
            instance_registry_path=self.root.parent / f"{self.root.name}-instances.json",
        )
        store = self._create_database()
        self._seed_action(store, kind="local_and_network_ban", ends_at=self.now + timedelta(hours=2),
                          created_at=self.now)
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-status", RiposteStatusScreen)
            warnings = str(screen.query_one("#riposte-warnings", Static).content)
            self.assertIn("absentes : omega-serv-riposte-6h, omega-serv-riposte-24h, omega-serv-riposte-7d", warnings)
            self.assertIn("omega-serv-active-defense (ban fixe de 24 h)", warnings)
            self.assertIn("Bans réseau passés à fail2ban : 1", str(screen.query_one("#riposte-status-body", Static).content))
            await self._press(pilot, "#back")
            await self._press(pilot, "#riposte-actions")
            await self._select_row(pilot, "#actions-table")
            self.assertIn("jail omega-serv-riposte-1h (1 h)", str(pilot.app.screen.query_one("#action-detail", Static).content))
            await self._press(pilot, "#revoke")
            self.assertIn("Seul le ban local est levé.", str(pilot.app.screen.query_one(".omega-choice-message", Static).content))
        installed["jails"] = None  # fail2ban absent
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            screen = await self._open(pilot, "riposte-status", RiposteStatusScreen)
            self.assertIn("fail2ban absent ou illisible", str(screen.query_one("#riposte-warnings", Static).content))
        store.close()

    async def test_tables_are_never_collapsed_to_the_header(self):
        """Piege connu : un DataTable 1fr dans une zone qui defile tombe a la ligne d'en-tete."""
        self._set_options()
        store = self._create_database()
        for index in range(6):
            self._seed_action(store, id=f"{index:012x}", ip=f"203.0.113.{index + 1}")
        app = OmegaServApp(self.container)
        async with app.run_test(size=(100, 30)) as pilot:
            screen = await self._open(pilot, "riposte-actions", RiposteActionsScreen)
            table = screen.query_one("#actions-table", DataTable)
            self.assertEqual(table.row_count, 6)
            self.assertGreaterEqual(table.region.height, 7)
            self.assertTrue(screen.query_one("#back", Button).region.height > 0)  # barre d'actions visible
        store.close()


if __name__ == "__main__":
    unittest.main()
