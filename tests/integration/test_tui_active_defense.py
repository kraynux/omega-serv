"""Tests d'integration de l'ecran combine "Active Securite" (retour
utilisateur 2026-09-12 : "un ecran TUI est bienvenu... piloter tout
depuis une interface" ; renomme et etendu le 2026-09-13 pour regrouper
Active Defense ET WAF - "le menu WAF va etre sorti du menu configuration
detaille... sur le MENU PRINCIPAL"). Meme discipline que le reste du
projet : vraie I/O SQLite reelle contre un fichier temporaire
(`build_active_defense_collaborators` reel injecte, jamais un double),
les repositories sont peuples DIRECTEMENT (`.save()`/`.create()`/
`.add_event()`) plutot qu'en rejouant tout le pipeline WAF ->
observe_threat -> incident (deja couvert par test_active_defense_server.py/
test_manage_incidents.py) - seul le CABLAGE des ecrans (lecture, actions,
navigation) est verifie ici. Doubles simples pour waf_test_runner/
blocklist_port_factory (memes raisons que l'ancien test_tui_server_config.py
avant le demenagement du menu WAF)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Button, DataTable, Input, Select, Static

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.start_server import build_active_defense_collaborators
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.active_defense.entities import (
    DeceptionAssignment,
    IncidentEvent,
    ThreatState,
)
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.active_defense_menu_screen import ActiveDefenseMenuScreen
from omega_serv.interfaces.tui.screens.active_defense_settings_screen import (
    ActiveDefenseSettingsScreen,
)
from omega_serv.interfaces.tui.screens.active_defense_simulate_screen import (
    ActiveDefenseSimulateScreen,
)
from omega_serv.interfaces.tui.screens.active_defense_status_screen import ActiveDefenseStatusScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.deception_screen import DeceptionScreen
from omega_serv.interfaces.tui.screens.home import HomeScreen
from omega_serv.interfaces.tui.screens.incidents_screen import IncidentsScreen
from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
from omega_serv.interfaces.tui.screens.threats_screen import ThreatsScreen
from omega_serv.interfaces.tui.screens.waf_custom_rule_screen import WafCustomRuleScreen
from omega_serv.interfaces.tui.screens.waf_custom_rule_wizard_screen import (
    WafCustomRuleWizardScreen,
)
from omega_serv.interfaces.tui.screens.waf_modules_screen import WafModulesScreen
from omega_serv.interfaces.tui.screens.waf_status_screen import WafStatusScreen
from omega_serv.interfaces.tui.screens.waf_test_screen import WafTestScreen

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


class _FakeBlocklistPort:
    def __init__(self) -> None:
        self.entries: dict[str, BlocklistEntry] = {}

    def is_blocked(self, ip: str) -> BlocklistEntry | None:
        return self.entries.get(ip)

    def list_entries(self) -> tuple[BlocklistEntry, ...]:
        return tuple(self.entries.values())

    def add_entry(self, entry: BlocklistEntry) -> None:
        self.entries[entry.network] = entry

    def remove_entry(self, network: str) -> bool:
        return self.entries.pop(network, None) is not None

    def purge_expired(self) -> int:
        return 0

    def count_auto_entries(self) -> int:
        return 0


def _fake_waf_test_runner(method, path, query, body, remote_ip, config, filesystem, project_root, clock):
    class _FakeDecision:
        action = "block"
        status_code = 403
        score = 100
        findings: list = []  # noqa: RUF012 - simple double de test, jamais sous-classe
        blocked_reason = "test"
        matched_zone_id = "default"

    class _FakeReport:
        decision = _FakeDecision()
        zone_id = "default"
        mode = "block"

    return _FakeReport()


def _run_ioc_export(incident, export_format, export_dir, filesystem):
    from omega_serv.infrastructure.exporters.csv_ioc_exporter import CsvIoCExporter
    from omega_serv.infrastructure.exporters.json_ioc_exporter import JsonIoCExporter

    exporters = {"json": JsonIoCExporter(filesystem, export_dir), "csv": CsvIoCExporter(filesystem, export_dir)}
    exporter = exporters.get(export_format)
    return None if exporter is None else exporter.export(incident)


def _run_incident_report_export(incident, export_dir, filesystem):
    from omega_serv.infrastructure.exporters.markdown_incident_report_exporter import (
        MarkdownIncidentReportExporter,
    )

    return MarkdownIncidentReportExporter(filesystem, export_dir).render(incident)


class _FakeServiceManager:
    """Retour utilisateur 2026-09-14 : "il faut qu'il puisse pas taper
    de commande a chaque fois qu'il change le mode de blocage ou met
    une nouvelle regle" - `is_active` False par defaut (n'affecte pas
    les tests existants qui ne testent pas ce comportement), bascule a
    True dans les tests dedies ci-dessous."""

    def __init__(self) -> None:
        self.active = False
        self.reload_calls: list[str] = []

    def manager_type(self):
        return "systemd"

    def is_active(self, service_name: str) -> bool:
        return self.active

    def reload(self, service_name: str) -> bool:
        self.reload_calls.append(service_name)
        return True


class TestTuiActiveDefense(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.fake_blocklist_port = _FakeBlocklistPort()
        self.fake_service_manager = _FakeServiceManager()
        self.container = DependencyContainer(
            project_root=self.root,
            active_defense_collaborators_factory=build_active_defense_collaborators,
            ioc_export_runner=_run_ioc_export,
            incident_report_export_runner=_run_incident_report_export,
            waf_test_runner=_fake_waf_test_runner,
            blocklist_port_factory=lambda config, filesystem, project_root, clock: self.fake_blocklist_port,
            service_manager_factory=lambda: self.fake_service_manager,
            instance_registry_path=self.root.parent / f"{self.root.name}-instances.json",
        )
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)

    def tearDown(self):
        self._tmp.cleanup()

    def _enable_active_defense(self, **settings) -> None:
        result = load_config(self.container.configuration, self.container.config_file)
        assert result.success and result.config is not None
        new_options = dict(result.config.options)
        new_options["active_defense"] = Option(name="active_defense", enabled=True, settings=settings)
        new_config = replace(result.config, options=new_options)
        self.container.configuration.save(self.container.config_file, new_config)

    def _seed(self):
        result = load_config(self.container.configuration, self.container.config_file)
        assert result.config is not None
        active_defense = build_active_defense_collaborators(result.config, self.container.project_root)
        assert active_defense is not None
        return active_defense

    async def _reach_home(self, pilot) -> None:
        await pilot.press("x")
        await pilot.pause()
        if isinstance(pilot.app.screen, TerminalWarningScreen):
            await pilot.click("#continue")
            await pilot.pause()
        self.assertIsInstance(pilot.app.screen, HomeScreen)

    async def _open_menu(self, pilot) -> None:
        pilot.app.screen.query_one("#active-defense", Button).press()
        await pilot.pause()
        self.assertIsInstance(pilot.app.screen, ActiveDefenseMenuScreen)

    async def _dismiss_restart_prompt(self, pilot) -> None:
        self.assertIsInstance(pilot.app.screen, ConfirmScreen)
        pilot.app.screen.query_one("#cancel", Button).press()
        await pilot.pause()

    async def test_menu_shows_group_mismatch_hint_when_detected(self):
        with patch(
            "omega_serv.interfaces.tui.screens.active_defense_menu_screen.is_missing_live_group",
            return_value=True,
        ):
            app = OmegaServApp(self.container)
            async with app.run_test(size=(120, 45)) as pilot:
                await self._reach_home(pilot)
                await self._open_menu(pilot)
                hint = str(pilot.app.screen.query_one("#group-mismatch-hint", Static).content)
                self.assertIn("deconnectez", hint)

    async def test_menu_shows_no_hint_when_group_is_fine(self):
        with patch(
            "omega_serv.interfaces.tui.screens.active_defense_menu_screen.is_missing_live_group",
            return_value=False,
        ):
            app = OmegaServApp(self.container)
            async with app.run_test(size=(120, 45)) as pilot:
                await self._reach_home(pilot)
                await self._open_menu(pilot)
                self.assertEqual(len(pilot.app.screen.query("#group-mismatch-hint")), 0)

    async def test_status_screen_shows_disabled_when_option_absent(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#status", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ActiveDefenseStatusScreen)
            self.assertIn("desactive", str(pilot.app.screen.query_one("#status-body", Static).content))

    async def test_status_screen_shows_enabled_details(self):
        self._enable_active_defense(mode="enforce", war_mode={"enabled": True}, deception={"enabled": True})
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#status", Button).press()
            await pilot.pause()
            body = str(pilot.app.screen.query_one("#status-body", Static).content)
            self.assertIn("mode=enforce", body)
            self.assertIn("Sources suivies : 0", body)

    async def test_threats_screen_lists_and_shows_detail(self):
        self._enable_active_defense()
        active_defense = self._seed()
        active_defense.threat_state_repository.save(
            ThreatState(
                subject_id="203.0.113.1:abcd", score=42, level="suspicious",
                updated_at=_NOW, expires_at=_NOW + timedelta(hours=2),
            )
        )
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#threats", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ThreatsScreen)
            table = pilot.app.screen.query_one("#threats-table", DataTable)
            self.assertEqual(table.row_count, 1)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            self.assertIn("203.0.113.1:abcd", str(pilot.app.screen.query_one("#threat-detail", Static).content))

    async def test_incidents_screen_lists_shows_timeline_and_closes(self):
        self._enable_active_defense()
        active_defense = self._seed()
        active_defense.incident_repository.create("inc-1", "203.0.113.1:abcd", _NOW)
        active_defense.incident_repository.add_event(
            "inc-1", IncidentEvent(occurred_at=_NOW, kind="opened", detail="score=80")
        )
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#incidents", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, IncidentsScreen)
            table = pilot.app.screen.query_one("#incidents-table", DataTable)
            self.assertEqual(table.row_count, 1)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            self.assertIn("opened", str(pilot.app.screen.query_one("#incident-detail", Static).content))

            pilot.app.screen.query_one("#close-incident", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#incidents-table", DataTable)
            self.assertEqual(table.get_row_at(0)[2], "closed")

    async def test_incidents_screen_exports_ioc_and_report(self):
        self._enable_active_defense()
        active_defense = self._seed()
        active_defense.incident_repository.create("inc-1", "203.0.113.1:abcd", _NOW)
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#incidents", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#incidents-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()

            pilot.app.screen.query_one("#export-ioc", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-format", Input).value = "json"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            export_dir = self.root / active_defense.config.storage.export_dir
            self.assertTrue(any(export_dir.glob("*.json")))

            pilot.app.screen.query_one("#generate-report", Button).press()
            await pilot.pause()
            self.assertTrue(any(export_dir.glob("*.md")))

    async def test_deception_screen_lists_and_releases(self):
        self._enable_active_defense()
        active_defense = self._seed()
        active_defense.deception_assignment_repository.save(
            DeceptionAssignment(
                subject_id="203.0.113.1:abcd", profile_name="fake_admin",
                assigned_at=_NOW, expires_at=_NOW + timedelta(hours=2),
            )
        )
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#deception", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, DeceptionScreen)
            table = pilot.app.screen.query_one("#deception-table", DataTable)
            self.assertEqual(table.row_count, 1)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#release", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#deception-table", DataTable).row_count, 0)

    async def test_simulate_screen_reports_a_projected_decision_without_writing_state(self):
        self._enable_active_defense(
            war_mode={"enabled": True, "thresholds": {"suspicious_score": 10, "hostile_score": 60}},
        )
        active_defense = self._seed()
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#simulate", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ActiveDefenseSimulateScreen)
            pilot.app.screen.query_one("#sim-score-input", Input).value = "65"
            pilot.app.screen.query_one("#simulate", Button).press()
            await pilot.pause()
            result = str(pilot.app.screen.query_one("#simulate-result", Static).content)
            self.assertIn("0 -> 65", result)
            self.assertIn("normal -> hostile", result)
            self.assertEqual(active_defense.threat_state_repository.list_all(), [])

    async def test_incidents_screen_auto_exports_ioc_on_close_when_configured(self):
        """Plan §"Mode guerre" : "produire un export IoC a la fermeture
        de l'incident" - IoCConfig.auto_export_on_close vaut True par
        defaut."""
        self._enable_active_defense()
        active_defense = self._seed()
        active_defense.incident_repository.create("inc-1", "203.0.113.1:abcd", _NOW)
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#incidents", Button).press()
            await pilot.pause()
            table = pilot.app.screen.query_one("#incidents-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#close-incident", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            export_dir = self.root / active_defense.config.storage.export_dir
            self.assertTrue((export_dir / "inc-1.json").exists())
            self.assertTrue((export_dir / "inc-1.csv").exists())
            self.assertTrue((export_dir / "inc-1.md").exists())

    async def test_back_buttons_return_to_menu(self):
        self._enable_active_defense()
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            for item_id, screen_cls in (
                ("status", ActiveDefenseStatusScreen), ("threats", ThreatsScreen),
                ("incidents", IncidentsScreen), ("deception", DeceptionScreen),
                ("simulate", ActiveDefenseSimulateScreen),
                ("waf-status", WafStatusScreen), ("waf-modules", WafModulesScreen),
                ("waf-test", WafTestScreen), ("waf-custom", WafCustomRuleScreen),
            ):
                pilot.app.screen.query_one(f"#{item_id}", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, screen_cls)
                pilot.app.screen.query_one("#back", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, ActiveDefenseMenuScreen)

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions - test non pertinent")
    async def test_status_screen_shows_a_clean_error_instead_of_crashing_on_permission_denied(self):
        self._enable_active_defense()
        restricted_dir = self.root / "var" / "lib"
        restricted_dir.mkdir(parents=True, exist_ok=True)
        restricted_dir.chmod(0o500)
        try:
            app = OmegaServApp(self.container)
            async with app.run_test(size=(120, 45)) as pilot:
                await self._reach_home(pilot)
                await self._open_menu(pilot)
                pilot.app.screen.query_one("#status", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, ActiveDefenseStatusScreen)
                body = str(pilot.app.screen.query_one("#status-body", Static).content)
                self.assertIn("acces", body)
                self.assertIn("session", body)

                pilot.app.screen.query_one("#back", Button).press()
                await pilot.pause()
                self.assertIsInstance(pilot.app.screen, ActiveDefenseMenuScreen)
        finally:
            restricted_dir.chmod(0o755)

    def _enable_waf(self, **settings) -> None:
        result = load_config(self.container.configuration, self.container.config_file)
        assert result.success and result.config is not None
        new_options = dict(result.config.options)
        new_options["waf"] = Option(name="waf", enabled=True, settings=settings)
        new_config = replace(result.config, options=new_options)
        self.container.configuration.save(self.container.config_file, new_config)

    async def test_waf_status_screen_shows_disabled_then_enabled(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-status", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WafStatusScreen)
            self.assertIn("desactive", str(pilot.app.screen.query_one("#status-body", Static).content))

            pilot.app.screen.query_one("#back", Button).press()
            await pilot.pause()
            self._enable_waf(mode="block", rules={"paths": ["secure/waf/rules/scanner-ua.json"]})
            pilot.app.screen.query_one("#waf-status", Button).press()
            await pilot.pause()
            body = str(pilot.app.screen.query_one("#status-body", Static).content)
            self.assertIn("mode=block", body)
            self.assertIn("scanner-ua.json", body)

    async def test_waf_modules_mode_save_and_test_and_blocklist_crud(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-modules", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WafModulesScreen)

            pilot.app.screen.query_one("#mode-input", Input).value = "block"
            pilot.app.screen.query_one("#save-mode", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
            self.assertIn('"mode": "block"', self.container.config_file.read_text())

            pilot.app.screen.query_one("#add-entry", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-network", Input).value = "203.0.113.5/32"
            pilot.app.screen.query_one("#df-reason", Input).value = "abuse"
            pilot.app.screen.query_one("#df-confirm_permanent", Input).value = "oui"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#blocklist-table", DataTable).row_count, 1)

            table = pilot.app.screen.query_one("#blocklist-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-entry", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#blocklist-table", DataTable).row_count, 0)

    async def test_waf_modules_save_mode_reloads_the_service_when_active(self):
        """Retour utilisateur 2026-09-14 : "il faut qu'il puisse pas
        taper de commande a chaque fois qu'il change le mode de
        blocage" - enregistrer le mode WAF declenche automatiquement un
        rechargement a chaud du service, SI un service actif existe
        pour ce repertoire (jamais une notification genante sinon)."""
        self.fake_service_manager.active = True
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-modules", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#mode-input", Input).value = "block"
            pilot.app.screen.query_one("#save-mode", Button).press()
            await pilot.pause()
            self.assertEqual(self.fake_service_manager.reload_calls, ["omega-serv"])

    async def test_waf_modules_save_mode_never_reloads_when_service_inactive(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-modules", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#mode-input", Input).value = "block"
            pilot.app.screen.query_one("#save-mode", Button).press()
            await pilot.pause()
            self.assertEqual(self.fake_service_manager.reload_calls, [])

    async def test_waf_modules_rule_paths_crud_via_picker(self):
        rules_dir = self.root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "aaa-first.json").write_text(
            '{"version": 1, "pack": "aaa-first", "enabled": true, '
            '"rules": [{"id": "R1", "description": "premiere regle", "scope": ["path"], "pattern": "x", "weight": 1}]}'
        )
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-modules", Button).press()
            await pilot.pause()

            pilot.app.screen.query_one("#add-rule-path", Button).press()
            await pilot.pause()
            select = pilot.app.screen.query_one("#pack-select", Select)
            self.assertEqual(str(select.value), "secure/waf/rules/aaa-first.json")
            description = str(pilot.app.screen.query_one("#pack-description").content)
            self.assertIn("aaa-first", description)
            self.assertIn("R1", description)

            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#rule-paths-table", DataTable).row_count, 1)

            table = pilot.app.screen.query_one("#rule-paths-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-rule-path", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#rule-paths-table", DataTable).row_count, 0)

    async def test_waf_test_screen_runs_a_real_test(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-test", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WafTestScreen)
            pilot.app.screen.query_one("#test", Button).press()
            await pilot.pause()
            self.assertIn("BLOCK", str(pilot.app.screen.query_one("#test-result").content))

    async def test_waf_custom_rule_add_and_delete_auto_references_pack(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-custom", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WafCustomRuleScreen)

            pilot.app.screen.query_one("#add-rule", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, WafCustomRuleWizardScreen)
            pilot.app.screen.query_one("#value-input", Input).value = "admin"
            pilot.app.screen.query_one("#description-input", Input).value = "bloque /admin"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()

            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")
            self.assertEqual(pilot.app.screen.query_one("#custom-rules-table", DataTable).row_count, 1)

            custom_pack = json.loads((self.root / "secure" / "waf" / "rules" / "custom.json").read_text())
            self.assertEqual(custom_pack["rules"][0]["id"], "CUSTOM-001")  # genere automatiquement
            self.assertEqual(custom_pack["rules"][0]["pattern"], "/admin(/|$)")
            self.assertEqual(custom_pack["rules"][0]["scope"], ["path"])

            saved_config = json.loads(self.container.config_file.read_text())
            self.assertIn(
                "secure/waf/rules/custom.json", saved_config["options"]["waf"]["rules"]["paths"],
            )

            table = pilot.app.screen.query_one("#custom-rules-table", DataTable)
            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-rule", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#custom-rules-table", DataTable).row_count, 0)

    async def test_waf_custom_rule_add_reloads_the_service_when_active(self):
        self.fake_service_manager.active = True
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-custom", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-rule", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#value-input", Input).value = "admin"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(self.fake_service_manager.reload_calls, ["omega-serv"])

    async def test_waf_custom_rule_rejects_invalid_pattern(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-custom", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-rule", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#detection-type-select", Select).value = "advanced"
            await pilot.pause()
            pilot.app.screen.query_one("#scope-input", Input).value = "path"
            pilot.app.screen.query_one("#pattern-input", Input).value = "(unclosed"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("invalide", str(pilot.app.screen.query_one("#form-error").content))
            self.assertEqual(pilot.app.screen.query_one("#custom-rules-table", DataTable).row_count, 0)

    async def test_waf_custom_rule_wizard_keyword_and_user_agent_modes(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 45)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#waf-custom", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-rule", Button).press()
            await pilot.pause()

            pilot.app.screen.query_one("#detection-type-select", Select).value = "user_agent"
            await pilot.pause()
            pilot.app.screen.query_one("#value-input", Input).value = "sqlmap"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

            custom_pack = json.loads((self.root / "secure" / "waf" / "rules" / "custom.json").read_text())
            self.assertEqual(custom_pack["rules"][0]["scope"], ["user_agent"])
            self.assertEqual(custom_pack["rules"][0]["pattern"], "sqlmap")

    async def test_settings_screen_opens_from_menu(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#settings", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ActiveDefenseSettingsScreen)

    async def test_settings_screen_enabling_war_mode_warns_restart_and_writes_config(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#settings", Button).press()
            await pilot.pause()
            self.assertEqual(pilot.app.screen.query_one("#war-enabled-input", Input).value, "non")
            pilot.app.screen.query_one("#war-enabled-input", Input).value = "oui"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            static_texts = [str(s.content) for s in pilot.app.screen.query(Static)]
            self.assertTrue(any("REDEMARRAGE COMPLET" in t for t in static_texts))
            await self._dismiss_restart_prompt(pilot)
            self.assertEqual(str(pilot.app.screen.query_one("#form-error").content), "")

        data = json.loads(self.container.config_file.read_text())
        self.assertTrue(data["options"]["active_defense"]["war_mode"]["enabled"])

    async def test_settings_screen_rejects_invalid_thresholds(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#settings", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#war-suspicious-input", Input).value = "90"
            pilot.app.screen.query_one("#war-hostile-input", Input).value = "10"
            pilot.app.screen.query_one("#save", Button).press()
            await pilot.pause()
            self.assertIn("suspicious_score", str(pilot.app.screen.query_one("#form-error").content))

    async def test_settings_screen_add_and_delete_deception_profile(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#settings", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-profile", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-name", Input).value = "fake_admin"
            pilot.app.screen.query_one("#df-match_attack_classes", Input).value = "scan, unknown"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._dismiss_restart_prompt(pilot)
            table = pilot.app.screen.query_one("#profiles-table", DataTable)
            self.assertEqual(table.row_count, 1)

            data = json.loads(self.container.config_file.read_text())
            profiles = data["options"]["active_defense"]["deception"]["profiles"]
            self.assertIn("fake_admin", profiles)
            self.assertEqual(profiles["fake_admin"]["match_attack_classes"], ["scan", "unknown"])

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-profile", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._dismiss_restart_prompt(pilot)
            self.assertEqual(pilot.app.screen.query_one("#profiles-table", DataTable).row_count, 0)

    async def test_settings_screen_add_and_delete_decoy_zone(self):
        app = OmegaServApp(self.container)
        async with app.run_test(size=(120, 50)) as pilot:
            await self._reach_home(pilot)
            await self._open_menu(pilot)
            pilot.app.screen.query_one("#settings", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#add-decoy-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#df-name", Input).value = "fake-admin-backend"
            pilot.app.screen.query_one("#df-upstreams", Input).value = "127.0.0.1:9001"
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._dismiss_restart_prompt(pilot)
            table = pilot.app.screen.query_one("#decoy-zones-table", DataTable)
            self.assertEqual(table.row_count, 1)

            data = json.loads(self.container.config_file.read_text())
            zones = data["options"]["active_defense"]["deception"]["decoy_zones"]
            self.assertIn("fake-admin-backend", zones)
            self.assertEqual(zones["fake-admin-backend"]["upstreams"][0]["port"], 9001)

            table.move_cursor(row=0)
            table.action_select_cursor()
            await pilot.pause()
            pilot.app.screen.query_one("#delete-decoy-zone", Button).press()
            await pilot.pause()
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            await self._dismiss_restart_prompt(pilot)
            self.assertEqual(pilot.app.screen.query_one("#decoy-zones-table", DataTable).row_count, 0)


if __name__ == "__main__":
    unittest.main()
