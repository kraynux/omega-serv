"""Assistant WAF Custom (types "CHARGER une liste") et ecran Custom a deux
sources - OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md lots 6 et 7. Vraie
OmegaServApp, vrais fichiers, vraies references du paquet."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from textual import events
from textual.widgets import Button, DataTable, Input, Select

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.path_list_editor_screen import PathListEditorScreen
from omega_serv.interfaces.tui.screens.waf_custom_rule_screen import WafCustomRuleScreen
from omega_serv.interfaces.tui.screens.waf_custom_rule_wizard_screen import (
    WafCustomRuleWizardScreen,
)
from omega_serv.interfaces.tui.screens.waf_keyword_list_settings_screen import (
    KeywordListSettingsScreen,
)

_KEYWORDS = "secure/waf/rules/keywords"
_SIZE = (180, 70)


class _CustomApp(OmegaServApp):
    def on_mount(self, event: events.Mount) -> None:
        event.prevent_default()
        self.push_screen(WafCustomRuleScreen(container=self._container))


class _ListsCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / _KEYWORDS).mkdir(parents=True)
        (self.root / "units").mkdir()
        self.check_errors: list[str] = []
        self.container = DependencyContainer(
            project_root=self.root, systemd_unit_dir=self.root / "units",
            instance_registry_path=self.root / "instances.json",
            config_check_runner=lambda *args: list(self.check_errors),
        )
        config = OmegaServConfig.from_dict({"options": {"waf": {
            "enabled": True, "mode": "block", "rules": {"paths": ["secure/waf/rules/custom.json"]},
        }}})
        self.container.configuration.save(self.container.config_file, config)

    def tearDown(self):
        self._tmp.cleanup()

    def config(self) -> dict:
        return json.loads(self.container.config_file.read_text())

    def keyword_lists(self) -> list[dict]:
        return self.config()["options"]["waf"]["rules"].get("keyword_lists", [])

    @staticmethod
    def notifications(pilot) -> list[str]:
        return [n.message for n in pilot.app._notifications]

    async def open_wizard(self, pilot) -> WafCustomRuleWizardScreen:
        await pilot.pause()
        pilot.app.screen.query_one("#add-rule", Button).press()
        await pilot.pause()
        wizard = pilot.app.screen
        self.assertIsInstance(wizard, WafCustomRuleWizardScreen)
        return wizard

    async def set_select(self, pilot, screen, selector: str, value: str) -> None:
        screen.query_one(selector, Select).value = value
        await pilot.pause()

    async def load_hostile_reference(self, pilot) -> None:
        wizard = await self.open_wizard(pilot)
        await self.set_select(pilot, wizard, "#detection-type-select", "list_path")
        await self.set_select(pilot, wizard, "#list-file-select", "ref:sensitive-paths-hostile.txt")
        wizard.query_one("#confirm", Button).press()
        await pilot.pause()

    def select_row(self, pilot, key: str) -> None:
        table = pilot.app.screen.query_one("#custom-rules-table", DataTable)
        table.move_cursor(row=table.get_row_index(key))
        table.action_select_cursor()


class TestWizardLoadsReference(_ListsCase):
    async def test_presets_then_explicit_load(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            wizard = await self.open_wizard(pilot)
            self.assertEqual(self.keyword_lists(), [], "rien de charge par defaut")
            await self.set_select(pilot, wizard, "#detection-type-select", "list_path")
            await self.set_select(pilot, wizard, "#list-file-select", "ref:sensitive-paths-hostile.txt")
            self.assertEqual(wizard.query_one("#list-gravity", Select).value, "observe")
            self.assertEqual(wizard.query_one("#list-anchor", Select).value, "any_segment")
            self.assertEqual(wizard.query_one("#list-recidive-count", Select).value, "2")
            self.assertTrue(wizard.query_one("#list-recidive-count", Select).disabled, "grise en Observation")
            self.assertEqual(str(wizard.query_one("#confirm", Button).label), "Charger")
            self.assertFalse(wizard.query_one("#value-input", Input).display)
            wizard.query_one("#confirm", Button).press()
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, WafCustomRuleScreen)
            entry = self.keyword_lists()[0]
            self.assertEqual((entry["id"], entry["match"], entry["observe_only"], entry["weight"], entry["anchor"]),
                             ("sensitive-paths-hostile", "path", True, 6, "any_segment"))
            reputation = self.config()["options"]["waf"]["reputation"]
            self.assertTrue(reputation["enabled"] and reputation["auto_block"])
            self.assertTrue((self.root / _KEYWORDS / "sensitive-paths-hostile.txt").exists())
            self.assertTrue(any("reputation activee" in m for m in self.notifications(pilot)))
            self.assertTrue(any("Observation" in m for m in self.notifications(pilot)))

            table = pilot.app.screen.query_one("#custom-rules-table", DataTable)
            row = table.get_row("list:sensitive-paths-hostile")
            self.assertEqual(row[0], "Liste")
            self.assertEqual(row[4], "298 entrees")
            self.assertEqual(row[5], "Observation")

    async def test_rule_types_still_produce_rules_and_keep_lists(self):
        """Non-regression du bug du 2026-10-18 : ajouter une regle effacait les listes."""
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            await self.load_hostile_reference(pilot)
            wizard = await self.open_wizard(pilot)
            wizard.query_one("#value-input", Input).value = "admin"
            wizard.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(len(self.keyword_lists()), 1, "la liste chargee est conservee")
            pack = json.loads((self.root / "secure" / "waf" / "rules" / "custom.json").read_text())
            self.assertEqual(pack["rules"][0]["pattern"], "/admin(/|$)")
            table = pilot.app.screen.query_one("#custom-rules-table", DataTable)
            self.assertEqual(table.row_count, 2)

    async def test_new_file(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            wizard = await self.open_wizard(pilot)
            await self.set_select(pilot, wizard, "#detection-type-select", "list_path")
            await self.set_select(pilot, wizard, "#list-file-select", "__new__")
            self.assertTrue(wizard.query_one("#list-new-name", Input).display)
            wizard.query_one("#list-new-name", Input).value = "Mes Chemins"
            await self.set_select(pilot, wizard, "#list-gravity", "6")
            wizard.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertTrue((self.root / _KEYWORDS / "mes-chemins.txt").read_text().startswith("# Liste de chemins"))
            entry = self.keyword_lists()[0]
            self.assertEqual((entry["id"], entry["observe_only"], entry["weight"]), ("mes-chemins", False, 6))

    async def test_keyword_list_with_scope(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            wizard = await self.open_wizard(pilot)
            await self.set_select(pilot, wizard, "#detection-type-select", "list_keyword")
            self.assertTrue(wizard.query_one("#list-scope", Select).display)
            self.assertFalse(wizard.query_one("#list-anchor", Select).display)
            await self.set_select(pilot, wizard, "#list-file-select", "__new__")
            wizard.query_one("#list-new-name", Input).value = "spam-referer"
            await self.set_select(pilot, wizard, "#list-scope", "referer")
            wizard.query_one("#confirm", Button).press()
            await pilot.pause()
            entry = self.keyword_lists()[0]
            self.assertEqual((entry["match"], entry["scope"]), ("substring", ["referer"]))

    async def test_invalid_list_is_refused_with_its_line(self):
        (self.root / _KEYWORDS / "perso.txt").write_text("/ok\n/robots.txt\n")
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            wizard = await self.open_wizard(pilot)
            await self.set_select(pilot, wizard, "#detection-type-select", "list_path")
            await self.set_select(pilot, wizard, "#list-file-select", "local:perso.txt")
            wizard.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertIn("ligne 2", str(pilot.app.screen.query_one("#form-error").render()))
            self.assertEqual(self.keyword_lists(), [])

    async def test_open_editor_from_wizard(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            wizard = await self.open_wizard(pilot)
            await self.set_select(pilot, wizard, "#detection-type-select", "list_path")
            await self.set_select(pilot, wizard, "#list-file-select", "ref:sensitive-paths-probe.txt")
            wizard.query_one("#list-open-editor", Button).press()
            await pilot.pause()
            editor = pilot.app.screen
            self.assertIsInstance(editor, PathListEditorScreen)
            self.assertIn("\n/admin\n", editor.text_area.text, "copie de la reference affichee")


class TestCustomScreenListActions(_ListsCase):
    async def test_modify_toggle_and_remove(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            await self.load_hostile_reference(pilot)
            self.select_row(pilot, "list:sensitive-paths-hostile")
            await pilot.pause()
            screen = pilot.app.screen
            self.assertEqual(str(screen.query_one("#delete-rule", Button).label), "Retirer")
            self.assertFalse(screen.query_one("#edit-list", Button).disabled)

            screen.query_one("#list-settings", Button).press()
            await pilot.pause()
            settings = pilot.app.screen
            self.assertIsInstance(settings, KeywordListSettingsScreen)
            await self.set_select(pilot, settings, "#settings-gravity", "6")
            await self.set_select(pilot, settings, "#settings-count", "2")
            await self.set_select(pilot, settings, "#settings-duration", "86400")
            settings.query_one("#settings-save", Button).press()
            await pilot.pause()
            entry = self.keyword_lists()[0]
            self.assertEqual((entry["observe_only"], entry["weight"], entry["escalation_threshold"],
                              entry["auto_block_duration_seconds"]), (False, 6, 2, 86400))
            row = pilot.app.screen.query_one("#custom-rules-table", DataTable).get_row("list:sensitive-paths-hostile")
            self.assertEqual(row[5], "Eleve, 2 en 10 min -> ban 24 h")

            self.select_row(pilot, "list:sensitive-paths-hostile")
            await pilot.pause()
            pilot.app.screen.query_one("#toggle-enabled", Button).press()
            await pilot.pause()
            self.assertFalse(self.keyword_lists()[0]["enabled"])

            self.select_row(pilot, "list:sensitive-paths-hostile")
            await pilot.pause()
            pilot.app.screen.query_one("#delete-rule", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            pilot.app.screen.query_one("#confirm", Button).press()
            await pilot.pause()
            self.assertEqual(self.keyword_lists(), [])
            self.assertTrue((self.root / _KEYWORDS / "sensitive-paths-hostile.txt").exists(), "fichier conserve")

    async def test_settings_change_refused_by_environment_check(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            await self.load_hostile_reference(pilot)
            self.check_errors = ["options.waf.rules.keyword_lists['sensitive-paths-hostile'] : route '/api/'"]
            self.select_row(pilot, "list:sensitive-paths-hostile")
            await pilot.pause()
            pilot.app.screen.query_one("#list-settings", Button).press()
            await pilot.pause()
            await self.set_select(pilot, pilot.app.screen, "#settings-gravity", "6")
            pilot.app.screen.query_one("#settings-save", Button).press()
            await pilot.pause()
            self.assertIn("Modification refusee", str(pilot.app.screen.query_one("#form-error").render()))
            self.assertTrue(self.keyword_lists()[0]["observe_only"])

    async def test_missing_file_is_flagged_not_crashing(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            await self.load_hostile_reference(pilot)
            (self.root / _KEYWORDS / "sensitive-paths-hostile.txt").unlink()
            pilot.app.screen._refresh()
            await pilot.pause()
            row = pilot.app.screen.query_one("#custom-rules-table", DataTable).get_row("list:sensitive-paths-hostile")
            self.assertEqual(row[4], "⚠ fichier absent")

    async def test_edit_list_opens_editor(self):
        async with _CustomApp(self.container).run_test(size=_SIZE) as pilot:
            await self.load_hostile_reference(pilot)
            self.select_row(pilot, "list:sensitive-paths-hostile")
            await pilot.pause()
            pilot.app.screen.query_one("#edit-list", Button).press()
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, PathListEditorScreen)


if __name__ == "__main__":
    unittest.main()
