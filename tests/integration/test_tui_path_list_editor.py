"""Editeur integre de listes de chemins - OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_
PATHS.md, lots 4 et 5. Tourne dans la VRAIE application (OmegaServApp : vrais
raccourcis globaux q/t/r/a/o, vraie garde de sortie, vrai CSS) dont seul le
demarrage est remplace pour ouvrir l'editeur directement.

Politique verifiee : souris d'abord, AUCUN raccourci clavier, seule la saisie
brute passe par le clavier (decision utilisateur 2026-10-18)."""
from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path

from textual import events
from textual.widgets import Button

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.interfaces.tui.app import OmegaServApp
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.path_list_editor_dialogs import (
    LogHitsScreen,
    ReferenceNewsScreen,
)
from omega_serv.interfaces.tui.screens.path_list_editor_screen import PathListEditorScreen

_RELATIVE = "secure/waf/rules/keywords/sensitive-paths-hostile.txt"
_SIZE = (160, 60)


class _EditorApp(OmegaServApp):
    def __init__(self, container: DependencyContainer, **editor_kwargs) -> None:
        super().__init__(container)
        self._editor_kwargs = editor_kwargs

    def on_mount(self, event: events.Mount) -> None:
        event.prevent_default()  # pas de splash/accueil : l'editeur directement
        self.push_screen(PathListEditorScreen(container=self._container, **self._editor_kwargs))


class _EditorCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "secure" / "waf" / "rules" / "keywords").mkdir(parents=True)
        (self.root / "var" / "log").mkdir(parents=True)
        (self.root / "units").mkdir()
        self.check_errors: list[str] = []
        self.save_config({})

    def tearDown(self):
        for path in self.root.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        self._tmp.cleanup()

    def save_config(self, options: dict) -> None:
        container = self.container()
        container.configuration.save(container.config_file, OmegaServConfig.from_dict({"options": options}))

    def container(self) -> DependencyContainer:
        return DependencyContainer(
            project_root=self.root,
            systemd_unit_dir=self.root / "units",
            instance_registry_path=self.root / "instances.json",
            config_check_runner=lambda *args: list(self.check_errors),
        )

    def list_file(self) -> Path:
        return self.root / _RELATIVE

    def app(self, **overrides) -> _EditorApp:
        kwargs = {"relative_path": _RELATIVE, "anchor": "any_segment", "title": "LISTE TEST"}
        kwargs.update(overrides)
        return _EditorApp(self.container(), **kwargs)

    @staticmethod
    def editor(pilot) -> PathListEditorScreen:
        screen = pilot.app.screen
        assert isinstance(screen, PathListEditorScreen), type(screen)
        return screen

    @staticmethod
    def notifications(pilot) -> list[str]:
        return [n.message for n in pilot.app._notifications]


class TestKeyboardPolicy(_EditorCase):
    async def test_global_letters_are_typed_as_text(self):
        self.list_file().write_text("/.env\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            theme_before = pilot.app.theme
            editor.text_area.move_cursor((1, 0))
            for key in ("q", "t", "r", "a", "o", "enter"):
                await pilot.press(key)
            await pilot.pause()
            self.assertEqual(editor.text_area.text, "/.env\nqtrao\n")
            self.assertEqual(pilot.app.theme, theme_before, "'t' ne doit pas changer le theme")
            self.assertIs(pilot.app.screen, editor, "'q'/'a'/'o' ne doivent ouvrir aucun ecran")

    async def test_editor_shortcuts_are_all_inert(self):
        self.list_file().write_text("/.env\n/.git/\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            editor.text_area.move_cursor((0, 2))
            await pilot.press("x")  # une vraie modification, que ctrl+z ne doit PAS annuler
            text_before, selection_before = editor.text_area.text, editor.text_area.selection
            for key in ("ctrl+z", "ctrl+y", "ctrl+x", "ctrl+v", "ctrl+k", "ctrl+u", "ctrl+w", "ctrl+a",
                        "ctrl+e", "ctrl+d", "ctrl+shift+k", "f6", "f7", "alt+delete", "alt+backspace",
                        "shift+left", "shift+right", "shift+home", "ctrl+left", "ctrl+right"):
                with self.subTest(key=key):
                    await pilot.press(key)
                    await pilot.pause()
                    self.assertEqual(editor.text_area.text, text_before)
                    self.assertEqual(editor.text_area.selection, selection_before)
                    self.assertIs(pilot.app.screen, editor)

    async def test_escape_and_f1_do_not_leave_the_editor(self):
        self.list_file().write_text("/.env\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            await pilot.press("x")
            for key in ("escape", "f1"):
                await pilot.press(key)
                await pilot.pause()
                self.assertIs(pilot.app.screen, editor, key)

    async def test_command_palette_is_neutralized_in_the_editor(self):
        self.list_file().write_text("/.env\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            await pilot.press("ctrl+p")
            await pilot.pause()
            self.assertIs(pilot.app.screen, editor)

    async def test_help_button_opens_this_screen_guide(self):
        from omega_serv.interfaces.tui.screens.guide_detail_screen import GuideDetailScreen

        self.list_file().write_text("/.env\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#editor-help")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, GuideDetailScreen)

    async def test_raw_editing_keys_still_work(self):
        self.list_file().write_text("/ab\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            editor.text_area.move_cursor((0, 3))
            await pilot.press("backspace", "left", "delete", "home", "c", "end", "d")
            self.assertEqual(editor.text_area.text, "c/d\n")

    async def test_focus_stays_in_text_after_every_button(self):
        self.list_file().write_text("/.env\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            for button_id in ("edit-select-line", "edit-copy", "edit-select-all", "search-next", "test-run"):
                with self.subTest(button=button_id):
                    await pilot.click(f"#{button_id}")
                    await pilot.pause()
                    self.assertIs(pilot.app.focused, editor.text_area)

    async def test_no_button_is_focusable(self):
        self.list_file().write_text("/.env\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            for button in self.editor(pilot).query(Button):
                self.assertFalse(button.can_focus, button.id)


class TestEditingButtons(_EditorCase):
    async def test_toolbar_edits_are_undoable(self):
        self.list_file().write_text("/a\n/b\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            editor.text_area.move_cursor((0, 0))
            await pilot.click("#edit-delete-line")
            await pilot.pause()
            self.assertEqual(editor.text_area.text, "/b\n")
            await pilot.click("#edit-undo")
            await pilot.pause()
            self.assertEqual(editor.text_area.text, "/a\n/b\n")
            await pilot.click("#edit-redo")
            await pilot.pause()
            self.assertEqual(editor.text_area.text, "/b\n")

    async def test_copy_paste_with_buttons(self):
        self.list_file().write_text("/a\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            await pilot.click("#edit-select-all")
            await pilot.click("#edit-copy")
            editor.text_area.move_cursor((1, 0))
            await pilot.click("#edit-paste")
            await pilot.pause()
            self.assertEqual(editor.text_area.text, "/a\n/a\n")

    async def test_search_selects_next_match(self):
        self.list_file().write_text("/a\n/xyz\n/b\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            editor.query_one("#search-input").value = "XY"
            await pilot.click("#search-next")
            await pilot.pause()
            self.assertEqual(editor.text_area.selected_text, "xy")

    async def test_clicking_a_diagnostic_jumps_to_its_line(self):
        self.list_file().write_text("/ok\n/ok2\nadmin\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause(0.5)
            editor = self.editor(pilot)
            await pilot.click("#editor-diagnostics", offset=(2, 1))
            await pilot.pause()
            self.assertEqual(editor.text_area.cursor_location[0], 2)


class TestSaveAndClose(_EditorCase):
    async def test_save_refused_while_errors_remain(self):
        self.list_file().write_text("/ok\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            editor.text_area.move_cursor((1, 0))
            for key in ("/", "r", "o", "b", "o", "t", "s", ".", "t", "x", "t"):
                await pilot.press(key)
            await pilot.click("#editor-save")
            await pilot.pause()
            self.assertEqual(self.list_file().read_text(), "/ok\n")
            self.assertTrue(any("refuse" in m for m in self.notifications(pilot)))

    async def test_valid_save_writes_0644_and_reports_unloaded_list(self):
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            editor.text_area.load_text("/.env\n")
            await pilot.click("#editor-save")
            await pilot.pause()
            self.assertEqual(self.list_file().read_text(), "/.env\n")
            self.assertEqual(stat.S_IMODE(self.list_file().stat().st_mode), 0o644)
            self.assertFalse(editor.has_unsaved_changes)
            self.assertTrue(any("pas encore chargee" in m for m in self.notifications(pilot)))

    async def test_loaded_list_with_check_error_is_not_reloaded(self):
        self.save_config({"waf": {"enabled": True, "rules": {"keyword_lists": [{
            "id": "sensitive-paths-hostile", "scope": ["path"], "match": "path", "file": _RELATIVE, "weight": 6,
        }]}}})
        self.check_errors = ["options.waf.rules.keyword_lists['sensitive-paths-hostile'] : conflit de route"]
        self.list_file().write_text("/.env\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            editor.text_area.load_text("/.env\n/.git/\n")
            await pilot.click("#editor-save")
            await pilot.pause()
            self.assertEqual(self.list_file().read_text(), "/.env\n/.git/\n", "la sauvegarde reste acquise")
            self.assertTrue(any("Rechargement NON effectue" in m for m in self.notifications(pilot)))

    async def test_external_modification_refused(self):
        self.list_file().write_text("/a\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            self.list_file().write_text("/modifie ailleurs\n")
            editor.text_area.load_text("/b\n")
            await pilot.click("#editor-save")
            await pilot.pause()
            self.assertEqual(self.list_file().read_text(), "/modifie ailleurs\n")
            self.assertTrue(any("modifie en dehors" in m for m in self.notifications(pilot)))

    async def test_close_with_changes_asks_confirmation(self):
        self.list_file().write_text("/a\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            await pilot.press("x")
            await pilot.click("#editor-close")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            await pilot.click("#cancel")
            await pilot.pause()
            self.assertIs(pilot.app.screen, editor)
            await pilot.click("#editor-close")
            await pilot.pause()
            await pilot.click("#confirm")
            await pilot.pause()
            self.assertNotIsInstance(pilot.app.screen, PathListEditorScreen)

    async def test_ctrl_q_warns_about_unsaved_changes(self):
        self.list_file().write_text("/a\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            await pilot.press("x")
            await pilot.press("ctrl+q")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertIn("non enregistrees", str(pilot.app.screen._message))

    async def test_read_only_directory(self):
        self.list_file().write_text("/a\n")
        (self.root / "secure" / "waf" / "rules" / "keywords").chmod(0o555)
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            self.assertTrue(editor.text_area.read_only)
            self.assertTrue(editor.query_one("#editor-save", Button).disabled)
            self.assertIn("LECTURE SEULE", str(editor.query_one("#editor-status").render()))


class TestTools(_EditorCase):
    async def test_tester_explains_current_text(self):
        self.list_file().write_text("/.env\n/api\n!/api/v1\n")
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            for value, expected in (("/blog/.env", "DETECTE par la ligne 1"), ("/api/v1/users", "AUTORISE"),
                                    ("/index.html", "aucune ligne")):
                with self.subTest(value=value):
                    editor.query_one("#test-input").value = value
                    await pilot.click("#test-run")
                    await pilot.pause()
                    self.assertIn(expected, str(editor.query_one("#test-result").render()))

    async def test_first_load_copies_reference_then_marks_retired_lines(self):
        async with self.app(reference_name="sensitive-paths-hostile.txt").run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            self.assertIn("\n/.env\n", editor.text_area.text, "premier chargement = copie de la reference")
            editor.text_area.load_text(editor.text_area.text.replace("\n/.env\n", "\n", 1))
            await pilot.click("#editor-save")
            await pilot.pause()
            saved = self.list_file().read_text()
            self.assertIn("#retire: /.env", saved)
            self.assertNotIn("\n/.env\n", saved)

    async def test_reference_news_adds_only_checked_entries(self):
        self.list_file().write_text("/.env\n")
        async with self.app(reference_name="sensitive-paths-hostile.txt").run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            await pilot.click("#tool-reference-news")
            await pilot.pause()
            dialog = pilot.app.screen
            self.assertIsInstance(dialog, ReferenceNewsScreen)
            await pilot.click("#reference-news", offset=(4, 1))  # coche la 1re nouveaute
            await pilot.pause()
            first = dialog._news[0]
            await pilot.click("#news-add")
            await pilot.pause()
            self.assertIn(f"#Ajouts depuis la reference\n{first}\n", editor.text_area.text)
            self.assertNotIn(dialog._news[1], editor.text_area.text)

    async def test_check_logs_then_add_directory_exception(self):
        self.list_file().write_text("/.env\n/*.log\n")
        (self.root / "var" / "log" / "access.log").write_text(
            '198.51.100.7 - - [18/Oct/2026:10:00:00 +0000] "GET /textfiles/bbs/a.log HTTP/1.1" 200 10 "-" "ua"\n'
            '198.51.100.8 - - [18/Oct/2026:10:00:01 +0000] "GET /.env HTTP/1.1" 403 10 "-" "ua"\n'
        )
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            await pilot.click("#tool-check-logs")
            await pilot.pause()
            dialog = pilot.app.screen
            self.assertIsInstance(dialog, LogHitsScreen)
            self.assertEqual([h.entry for h in dialog._hits], ["/*.log"], "/.env n'a jamais reussi (403)")
            await pilot.click("#log-hits", offset=(2, 1))
            await pilot.pause()
            await pilot.click("#hit-exception-dir")
            await pilot.pause()
            self.assertTrue(editor.text_area.text.endswith("!/textfiles/bbs/\n"))

    async def test_fix_rights_with_real_service_account(self):
        import pwd
        try:
            pwd.getpwnam("omega-serv")
        except KeyError:
            self.skipTest("compte omega-serv absent de cette machine")
        (self.root / "units" / "omega-serv.service").write_text("[Service]\nUser=omega-serv\n")
        self.list_file().write_text("/.env\n")
        self.root.chmod(0o700)
        async with self.app().run_test(size=_SIZE) as pilot:
            await pilot.pause()
            editor = self.editor(pilot)
            self.assertIn("ATTENTION", str(editor.query_one("#editor-status").render()))
            await pilot.click("#tool-fix-rights")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            await pilot.click("#confirm")
            await pilot.pause()
            self.assertIn("lisible par le compte omega-serv", str(editor.query_one("#editor-status").render()))


if __name__ == "__main__":
    unittest.main()
