"""Fenetres de l'editeur de listes de chemins (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md, lots 4.5/4.6) - souris uniquement, comme l'editeur :
aucun raccourci, aucun widget focalisable (tableau et liste a cocher se
cliquent), boutons non focalisables."""
from __future__ import annotations

import posixpath
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Center, Horizontal, Middle, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, SelectionList, Static

from omega_serv.application.security.path_list_tools import LogHit
from omega_serv.interfaces.tui.screens.text_file_editor_screen import MouseButton

LogHitAction = tuple[str, str]  # ("exception", "/chemin") | ("delete", "<numero de ligne>")


class LogHitsScreen(ModalScreen[LogHitAction | None], inherit_bindings=False):
    """Resultat de "Verifier contre mes logs" : chaque ligne de la liste qui
    aurait touche des requetes REUSSIES. Une action a la fois (les numeros
    de ligne changent apres une suppression)."""
    BINDINGS: ClassVar[list[BindingType]] = []
    DEFAULT_CSS = """
    LogHitsScreen #log-hits { height: auto; max-height: 20; }
    """

    def __init__(self, hits: tuple[LogHit, ...], scanned_lines: int) -> None:
        super().__init__()
        self._hits = hits
        self._scanned_lines = scanned_lines
        self._selected: LogHit | None = None

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-confirm-box"):
            yield Static("VERIFIER CONTRE MES LOGS", classes="omega-confirm-title")
            yield Static(
                f"{len(self._hits)} ligne(s) de la liste auraient touche des requetes REUSSIES (2xx/3xx) "
                f"parmi les {self._scanned_lines} dernieres lignes du journal d'acces. Cliquez une ligne, "
                "puis choisissez : exception pour le chemin vu, exception pour son dossier, ou suppression.",
                classes="omega-hint",
            )
            yield DataTable(id="log-hits")
            yield Static("", id="log-hit-selected", classes="omega-hint")
            with Horizontal(classes="omega-confirm-buttons"):
                yield MouseButton("Exception : ce chemin", id="hit-exception-path", disabled=True)
                yield MouseButton("Exception : son dossier", id="hit-exception-dir", disabled=True)
                yield MouseButton("Supprimer la ligne", id="hit-delete", variant="error", disabled=True)
                yield MouseButton("Fermer", id="hit-close", variant="primary")

    def on_mount(self) -> None:
        table = self.query_one("#log-hits", DataTable)
        table.can_focus = False
        table.cursor_type = "row"
        table.add_columns("Ligne", "Entree", "Requetes reussies", "Exemple")
        for index, hit in enumerate(self._hits):
            table.add_row(str(hit.line), hit.entry, str(hit.hits), hit.examples[0], key=str(index))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected = self._hits[int(str(event.row_key.value))]
        self.query_one("#log-hit-selected", Static).update(
            f"Ligne {self._selected.line} ({self._selected.entry}) - exemples : {', '.join(self._selected.examples)}"
        )
        for button_id in ("hit-exception-path", "hit-exception-dir", "hit-delete"):
            self.query_one(f"#{button_id}", MouseButton).disabled = False

    def on_button_pressed(self, event: MouseButton.Pressed) -> None:
        button_id = event.button.id
        if button_id == "hit-close" or self._selected is None:
            self.dismiss(None)
            return
        example = self._selected.examples[0]
        if button_id == "hit-exception-path":
            self.dismiss(("exception", example))
        elif button_id == "hit-exception-dir":
            directory = posixpath.dirname(example.rstrip("/")) or "/"
            self.dismiss(("exception", directory.rstrip("/") + "/"))
        elif button_id == "hit-delete":
            self.dismiss(("delete", str(self._selected.line)))


class ReferenceNewsScreen(ModalScreen[list[str] | None], inherit_bindings=False):
    """"Nouveautes de la reference" : entrees de la reference absentes de la
    liste locale et jamais retirees volontairement - rien n'est ajoute sans
    etre coche (jamais de fusion automatique, §3.11)."""
    BINDINGS: ClassVar[list[BindingType]] = []
    DEFAULT_CSS = """
    ReferenceNewsScreen #reference-news { height: auto; max-height: 20; }
    """

    def __init__(self, news: tuple[str, ...]) -> None:
        super().__init__()
        self._news = news

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-confirm-box"):
            yield Static("NOUVEAUTES DE LA REFERENCE", classes="omega-confirm-title")
            yield Static(
                f"{len(self._news)} entree(s) de la reference livree avec omega-serv ne sont pas dans "
                "votre liste. Cochez celles a ajouter (clic).",
                classes="omega-hint",
            )
            yield SelectionList[str](*((entry, entry, False) for entry in self._news), id="reference-news")
            with Horizontal(classes="omega-confirm-buttons"):
                yield MouseButton("Tout cocher", id="news-all")
                yield MouseButton("Tout decocher", id="news-none")
                yield MouseButton("Ajouter la selection", id="news-add", variant="primary")
                yield MouseButton("Fermer", id="news-close")

    def on_mount(self) -> None:
        self.query_one("#reference-news", SelectionList).can_focus = False

    def on_button_pressed(self, event: MouseButton.Pressed) -> None:
        selection: SelectionList[str] = self.query_one("#reference-news", SelectionList)
        if event.button.id == "news-all":
            selection.select_all()
        elif event.button.id == "news-none":
            selection.deselect_all()
        elif event.button.id == "news-add":
            chosen = [entry for entry in self._news if entry in selection.selected]
            self.dismiss(chosen or None)
        else:
            self.dismiss(None)
