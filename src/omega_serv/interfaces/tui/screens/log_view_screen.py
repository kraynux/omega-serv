"""Ecran "Voir les logs" (gestion des logs, refonte menu 2026-10-15,
OMEGA-LOG_PLAN §3/§7) : selection d'un ou plusieurs logs EXCLUSIVEMENT
depuis la Bibliotheque (aucun import manuel ici - evite de dupliquer la
responsabilite de l'ecran Bibliotheque) + choix du viewer, avec la
regle de compatibilite (`domain/logs/viewer_type.py::allowed_viewers`) :
1 log -> les 3 viewers ; 2+ logs -> lnav uniquement. Selection par
NUMEROS separes par des virgules - meme convention que la fusion
multi-fichiers de `lnav_screen.py`."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.logs.library import list_library
from omega_serv.domain.logs.library import LogFile
from omega_serv.domain.logs.viewer_type import ViewerType, allowed_viewers
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.lnav_screen import LnavScreen
from omega_serv.interfaces.tui.screens.log_simple_viewer_screen import LogSimpleViewerScreen
from omega_serv.interfaces.tui.screens.log_viewer_screen import LogViewerScreen
from omega_serv.interfaces.tui.widgets.log_library_table import LogLibraryTable

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class LogViewScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._entries: list[LogFile] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("VOIR LES LOGS", classes="omega-title")
            yield Static(
                "Logs references dans la Bibliotheque uniquement - importez-en "
                "d'autres depuis l'ecran Bibliotheque.",
                classes="omega-hint",
            )
            yield Static("", id="view-error", classes="omega-hint")
            yield LogLibraryTable(id="library-table")
            yield Static("Numeros ci-dessus, separes par des virgules (ex: 1,3)", classes="omega-subtitle")
            yield Input(placeholder="ex: 1,3", id="selection-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Voir (simple)", id="view-simple", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Voir (classique)", id="view-classic")
                with Container(classes="omega-btn-frame"):
                    yield Button("Voir (lnav)", id="view-lnav")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._entries = list_library(self._container.build_log_library_repository())
        self.query_one("#library-table", LogLibraryTable).load(self._entries)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
        elif button_id == "view-simple":
            self._open(ViewerType.SIMPLE)
        elif button_id == "view-classic":
            self._open(ViewerType.CLASSIC)
        elif button_id == "view-lnav":
            self._open(ViewerType.LNAV)

    def _selected_paths(self) -> list[str] | None:
        error_widget = self.query_one("#view-error", Static)
        raw = self.query_one("#selection-input", Input).value.strip()
        if not raw:
            error_widget.update("Saisissez au moins un numero de ligne.")
            return None
        paths: list[str] = []
        for token in raw.split(","):
            token = token.strip()
            if not token.isdigit() or not (1 <= int(token) <= len(self._entries)):
                error_widget.update(f"Numero invalide : {token!r}.")
                return None
            paths.append(self._entries[int(token) - 1].path)
        error_widget.update("")
        return paths

    def _open(self, viewer: ViewerType) -> None:
        paths = self._selected_paths()
        if paths is None:
            return
        allowed = allowed_viewers(len(paths))
        if viewer not in allowed:
            self.query_one("#view-error", Static).update(
                f"{len(paths)} log(s) selectionne(s) : seul {allowed[-1].value} est compatible."
            )
            return

        if viewer == ViewerType.SIMPLE:
            self.app.push_screen(LogSimpleViewerScreen(container=self._container, path=paths[0]))
        elif viewer == ViewerType.CLASSIC:
            self.app.push_screen(LogViewerScreen(container=self._container, path=paths[0]))
        else:
            self.app.push_screen(LnavScreen(container=self._container, preset_paths=tuple(paths)))
