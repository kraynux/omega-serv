"""Editeur de fichier texte integre, GENERIQUE (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md §3.6) - aucun editeur externe. Specialise par
`PathListEditorScreen` pour les listes de chemins ; reutilisable plus tard
pour d'autres fichiers texte (unification de la suite).

Politique clavier STRICTE (decision utilisateur 2026-10-18, verifiee au
Pilot) :
- l'ecran n'herite d'AUCUN raccourci (`inherit_bindings=False`) : Echap et F1
  sont inertes - un Echap herite d'OmegaScreen fermait l'editeur et perdait
  les modifications ;
- la zone de texte est un `RawTextArea` (saisie brute seulement) ;
- tous les boutons sont NON focalisables : le clavier reste toujours dans la
  zone de texte ou un champ de saisie, donc les lettres q/t/r/a/o (raccourcis
  globaux de l'application) y sont tapees comme du texte ;
- tableau des diagnostics non focalisable (clic seulement) ;
- pas de Footer : il n'y a aucun raccourci a annoncer.
Toute action passe par un clic."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, DataTable, Header, Input, Static
from textual.widgets.text_area import Selection

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen, show_contextual_help
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.widgets.raw_text_area import RawTextArea

_ANALYSIS_DELAY_SECONDS = 0.3


class MouseButton(Button):
    """Bouton cliquable mais jamais focalisable (politique clavier ci-dessus)."""
    can_focus = False


@dataclass(frozen=True)
class EditorDiagnostic:
    line: int
    severity: str  # "error" | "warning"
    message: str


@dataclass(frozen=True)
class EditorAnalysis:
    summary: str
    diagnostics: tuple[EditorDiagnostic, ...] = field(default_factory=tuple)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "error")


_EDIT_BUTTONS: tuple[tuple[str, str], ...] = (
    ("edit-undo", _("Annuler la modif")),
    ("edit-redo", _("Rétablir")),
    ("edit-cut", _("Couper")),
    ("edit-copy", _("Copier")),
    ("edit-paste", _("Coller")),
    ("edit-select-line", _("Sélectionner la ligne")),
    ("edit-select-all", _("Tout sélectionner")),
    ("edit-delete-line", _("Supprimer la ligne")),
)
_WRITE_BUTTONS = frozenset({"edit-undo", "edit-redo", "edit-cut", "edit-paste", "edit-delete-line", "editor-save"})


def offset_to_location(text: str, offset: int) -> tuple[int, int]:
    before = text[:offset]
    row = before.count("\n")
    return row, offset - (before.rfind("\n") + 1)


def location_to_offset(text: str, location: tuple[int, int]) -> int:
    row, column = location
    lines = text.split("\n")
    return sum(len(line) + 1 for line in lines[:row]) + column


class TextFileEditorScreen(OmegaScreen, inherit_bindings=False):
    """Herite d'OmegaScreen pour `_maybe_suspend` (rechargement qui peut demander
    sudo) et la compatibilite avec notify_reload_required - JAMAIS ses
    raccourcis (Echap/F1/fleches) : inherit_bindings=False."""

    BINDINGS: ClassVar[list[BindingType]] = []
    # Lu par OmegaServApp.check_action : neutralise la palette de commandes (ctrl+p).
    BLOCKS_GLOBAL_SHORTCUTS: ClassVar[bool] = True
    DEFAULT_CSS = """
    TextFileEditorScreen #editor-text { height: 1fr; min-height: 8; }
    TextFileEditorScreen #editor-diagnostics { height: auto; max-height: 6; }
    TextFileEditorScreen .editor-row { height: auto; }
    TextFileEditorScreen .editor-row > Input { width: 1fr; }
    TextFileEditorScreen .editor-row > Static { width: auto; padding: 1 1 0 0; }
    TextFileEditorScreen #test-result { width: 1fr; }
    """

    def __init__(self, *, title: str, text: str, read_only_reason: str | None = None) -> None:
        super().__init__()
        self._title = title
        self._initial_text = text
        self._saved_text = text
        self._read_only_reason = read_only_reason
        self._analysis_timer: Timer | None = None
        self._analysis = EditorAnalysis(summary="")

    # ---- points d'extension (sous-classes) --------------------------------
    def analyze(self, text: str) -> EditorAnalysis:
        return EditorAnalysis(summary=_("{count} ligne(s)").format(count=len(text.splitlines())))

    def supports_test(self) -> bool:
        return False

    def test_value(self, text: str, value: str) -> str:
        return ""

    def extra_tools(self) -> tuple[tuple[str, str], ...]:
        return ()

    def handle_extra_tool(self, tool_id: str) -> None:
        return None

    def save(self, text: str) -> tuple[bool, str]:
        """(enregistre ?, message a afficher). Le texte n'a aucune erreur."""
        return False, _("enregistrement non disponible")

    def status_text(self) -> str:
        return ""

    # ---- composition -------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(self._title, classes="omega-title")
            yield Static("", id="editor-summary", classes="omega-hint")
            yield RawTextArea(
                self._initial_text, id="editor-text", show_line_numbers=True, soft_wrap=False,
                read_only=self._read_only_reason is not None,
            )
            with Horizontal(classes="omega-actions editor-row"):
                for button_id, label in _EDIT_BUTTONS:
                    yield MouseButton(label, id=button_id)
            with Horizontal(classes="omega-actions editor-row"):
                yield Static(_("Rechercher"))
                yield Input(placeholder=_("texte à chercher"), id="search-input")
                yield MouseButton(_("Précédent"), id="search-prev")
                yield MouseButton(_("Suivant"), id="search-next")
            if self.supports_test():
                with Horizontal(classes="omega-actions editor-row"):
                    yield Static(_("Tester"))
                    yield Input(placeholder="/chemin/a/tester", id="test-input")
                    yield MouseButton(_("Tester"), id="test-run")
                    yield Static("", id="test-result")
            if self.extra_tools():
                with Horizontal(classes="omega-actions editor-row"):
                    for tool_id, label in self.extra_tools():
                        yield MouseButton(label, id=tool_id)
            yield DataTable(id="editor-diagnostics")
            yield Static("", id="editor-status", classes="omega-hint")
            with Horizontal(classes="omega-actions editor-row"):
                yield MouseButton(_("Enregistrer et appliquer"), id="editor-save", variant="primary")
                yield MouseButton(_("Fermer"), id="editor-close")
                yield MouseButton(_("Aide"), id="editor-help")

    def on_mount(self) -> None:
        table = self.query_one("#editor-diagnostics", DataTable)
        table.can_focus = False
        table.cursor_type = "row"
        table.add_columns(_("Ligne"), _("Type"), _("Message"))
        if self._read_only_reason is not None:
            for button_id in _WRITE_BUTTONS:
                self.query_one(f"#{button_id}", Button).disabled = True
        self._run_analysis()
        self.refresh_status()
        self.text_area.focus()

    # ---- etat ----------------------------------------------------------------
    @property
    def text_area(self) -> RawTextArea:
        return self.query_one("#editor-text", RawTextArea)

    @property
    def has_unsaved_changes(self) -> bool:
        return self.text_area.text != self._saved_text

    def mark_saved(self, text: str) -> None:
        self._saved_text = text
        self.refresh_status()

    def refresh_status(self) -> None:
        parts = []
        if self._read_only_reason is not None:
            parts.append(_("LECTURE SEULE : {read_only_reason}").format(read_only_reason=self._read_only_reason))
        elif self.is_mounted and self.has_unsaved_changes:
            parts.append(_("modifié (non enregistré)"))
        else:
            parts.append(_("enregistré"))
        extra = self.status_text()
        if extra:
            parts.append(extra)
        self.query_one("#editor-status", Static).update(" · ".join(parts))

    def notify_message(self, message: str, *, error: bool = False) -> None:
        self.app.notify(message, severity="error" if error else "information", timeout=8)

    # ---- analyse en direct (temporisee, jamais un raccourci) -----------------
    def on_text_area_changed(self, event: RawTextArea.Changed) -> None:
        if self._analysis_timer is not None:
            self._analysis_timer.stop()
        self._analysis_timer = self.set_timer(_ANALYSIS_DELAY_SECONDS, self._run_analysis)
        self.refresh_status()

    def _run_analysis(self) -> None:
        self._analysis = self.analyze(self.text_area.text)
        self.query_one("#editor-summary", Static).update(self._analysis.summary)
        table = self.query_one("#editor-diagnostics", DataTable)
        table.clear()
        for index, diagnostic in enumerate(self._analysis.diagnostics):
            table.add_row(
                str(diagnostic.line) if diagnostic.line else "-",
                _("erreur") if diagnostic.severity == "error" else _("avertissement"),
                diagnostic.message,
                key=str(index),
            )
        table.display = bool(self._analysis.diagnostics)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "editor-diagnostics":
            return
        diagnostic = self._analysis.diagnostics[int(str(event.row_key.value))]
        if diagnostic.line:
            self.go_to_line(diagnostic.line)

    def go_to_line(self, line: int) -> None:
        self.text_area.move_cursor((line - 1, 0), select=False, center=True)
        self.text_area.select_line(line - 1)
        self.text_area.focus()

    # ---- actions (boutons uniquement) --------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        text_area = self.text_area
        edit_actions = {
            "edit-undo": text_area.undo,
            "edit-redo": text_area.redo,
            "edit-cut": text_area.action_cut,
            "edit-copy": text_area.action_copy,
            "edit-paste": text_area.action_paste,
            "edit-select-line": text_area.action_select_line,
            "edit-select-all": text_area.select_all,
            "edit-delete-line": text_area.action_delete_line,
        }
        if button_id in edit_actions:
            edit_actions[button_id]()
        elif button_id in ("search-next", "search-prev"):
            self._search(forward=button_id == "search-next")
        elif button_id == "test-run":
            value = self.query_one("#test-input", Input).value.strip()
            self.query_one("#test-result", Static).update(self.test_value(text_area.text, value) if value else "")
        elif button_id == "editor-save":
            self._save()
        elif button_id == "editor-close":
            self._close()
        elif button_id == "editor-help":
            # F1 est volontairement inactif (aucun raccourci) : l'aide passe par un clic.
            show_contextual_help(self.app, type(self).__name__)
        else:
            self.handle_extra_tool(button_id)
        if button_id not in ("editor-close", "editor-help") and self.is_mounted:
            text_area.focus()

    def _search(self, *, forward: bool) -> None:
        needle = self.query_one("#search-input", Input).value
        if not needle:
            return
        text = self.text_area.text
        haystack, target = text.lower(), needle.lower()
        selection = self.text_area.selection
        if forward:
            start = location_to_offset(text, selection.end)
            found = haystack.find(target, start)
            if found == -1:
                found = haystack.find(target)
        else:
            start = location_to_offset(text, selection.start)
            found = haystack.rfind(target, 0, max(0, start))
            if found == -1:
                found = haystack.rfind(target)
        if found == -1:
            self.notify_message(_("'{needle}' introuvable").format(needle=needle))
            return
        self.text_area.selection = Selection(
            offset_to_location(text, found), offset_to_location(text, found + len(needle)),
        )
        self.text_area.scroll_cursor_visible(center=True)

    def _save(self) -> None:
        if self._read_only_reason is not None:
            return
        self._run_analysis()
        if self._analysis.error_count:
            self.notify_message(
                _("Enregistrement refusé : {error_count} erreur(s) à corriger (voir la liste).").format(error_count=self._analysis.error_count),
                error=True,
            )
            return
        saved, message = self.save(self.text_area.text)
        self.notify_message(message, error=not saved)
        self.refresh_status()

    def _close(self) -> None:
        if not self.has_unsaved_changes:
            self.dismiss()
            return
        self.app.push_screen(
            ConfirmScreen(
                title=_("FERMER SANS ENREGISTRER ?"),
                message=_("Les modifications non enregistrées seront perdues."),
            ),
            self._close_if_confirmed,
        )

    def _close_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.dismiss()

    # ---- edition programmatique (outils), toujours annulable ---------------
    def append_lines(self, lines: list[str]) -> None:
        text_area = self.text_area
        text = text_area.text
        end = offset_to_location(text, len(text))
        prefix = "" if not text or text.endswith("\n") else "\n"
        text_area.insert(prefix + "\n".join(lines) + "\n", end)

    def delete_line(self, line: int) -> None:
        self.text_area.delete((line - 1, 0), (line, 0))
