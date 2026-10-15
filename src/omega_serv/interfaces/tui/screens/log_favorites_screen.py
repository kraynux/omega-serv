"""Ecran Favoris (gestion des logs, refonte menu 2026-10-15, OMEGA-LOG_
PLAN §3/§7) : constitution et liste des favoris (source = Bibliotheque),
lancement direct depuis cet ecran. Meme convention de selection par
numeros que `log_view_screen.py`."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from omega_serv.application.logs.favorites import create_favorite, list_favorites, remove_favorite
from omega_serv.application.logs.library import list_library
from omega_serv.domain.logs.library import LogFile
from omega_serv.domain.logs.viewer_type import ViewerType
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.lnav_screen import LnavScreen
from omega_serv.interfaces.tui.screens.log_simple_viewer_screen import LogSimpleViewerScreen
from omega_serv.interfaces.tui.screens.log_viewer_screen import LogViewerScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class LogFavoritesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._library_entries: list[LogFile] = []
        self._selected_favorite: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("FAVORIS", classes="omega-title")
            yield Static("", id="favorites-error", classes="omega-hint")

            yield DataTable(id="favorites-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Lancer", id="launch", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete", variant="error")

            yield Static("Creer un favori (depuis la Bibliotheque)", classes="omega-subtitle")
            yield DataTable(id="library-table")
            yield Input(placeholder="Numeros separes par des virgules (ex: 1,3)", id="selection-input")
            with Horizontal(classes="omega-actions"):
                yield Input(placeholder="Nom du favori", id="name-input")
                yield Select[str](
                    [(v.value, v.value) for v in ViewerType], value=ViewerType.SIMPLE.value, id="viewer-select",
                )
                with Container(classes="omega-btn-frame"):
                    yield Button("Enregistrer", id="save")

            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#favorites-table", DataTable).cursor_type = "row"
        self.query_one("#favorites-table", DataTable).add_columns("Nom", "Logs", "Viewer")
        self.query_one("#library-table", DataTable).cursor_type = "row"
        self.query_one("#library-table", DataTable).add_columns("#", "Chemin")
        self._refresh_favorites()
        self._refresh_library()

    def _refresh_favorites(self) -> None:
        table = self.query_one("#favorites-table", DataTable)
        table.clear()
        for fav in list_favorites(self._container.build_log_favorite_repository()):
            table.add_row(fav.name, ", ".join(fav.paths), fav.viewer.value, key=fav.name)

    def _refresh_library(self) -> None:
        self._library_entries = list_library(self._container.build_log_library_repository())
        table = self.query_one("#library-table", DataTable)
        table.clear()
        for idx, entry in enumerate(self._library_entries, start=1):
            table.add_row(str(idx), entry.path)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "favorites-table":
            row = event.data_table.get_row_at(event.cursor_row)
            self._selected_favorite = str(row[0]) if row else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
        elif button_id == "launch":
            self._launch()
        elif button_id == "delete":
            self._delete()
        elif button_id == "save":
            self._save()

    def _launch(self) -> None:
        error_widget = self.query_one("#favorites-error", Static)
        if self._selected_favorite is None:
            error_widget.update("Selectionnez un favori.")
            return
        favorite = next(
            (f for f in list_favorites(self._container.build_log_favorite_repository())
             if f.name == self._selected_favorite),
            None,
        )
        if favorite is None:
            return
        error_widget.update("")
        if favorite.viewer == ViewerType.SIMPLE:
            self.app.push_screen(LogSimpleViewerScreen(container=self._container, path=favorite.paths[0]))
        elif favorite.viewer == ViewerType.CLASSIC:
            self.app.push_screen(LogViewerScreen(container=self._container, path=favorite.paths[0]))
        else:
            self.app.push_screen(
                LnavScreen(container=self._container, preset_paths=favorite.paths, auto_launch=True)
            )

    def _delete(self) -> None:
        error_widget = self.query_one("#favorites-error", Static)
        if self._selected_favorite is None:
            error_widget.update("Selectionnez un favori.")
            return
        name = self._selected_favorite
        self.app.push_screen(
            ConfirmScreen(title="SUPPRIMER CE FAVORI ?", message=name),
            lambda confirmed: self._delete_if_confirmed(confirmed, name),
        )

    def _delete_if_confirmed(self, confirmed: bool | None, name: str) -> None:
        if not confirmed:
            return
        remove_favorite(self._container.build_log_favorite_repository(), name)
        self._selected_favorite = None
        self.query_one("#favorites-error", Static).update("")
        self._refresh_favorites()

    def _save(self) -> None:
        error_widget = self.query_one("#favorites-error", Static)
        raw_selection = self.query_one("#selection-input", Input).value.strip()
        name = self.query_one("#name-input", Input).value.strip()
        viewer_value = self.query_one("#viewer-select", Select).value

        paths: list[str] = []
        for token in raw_selection.split(","):
            token = token.strip()
            if not token:
                continue
            if not token.isdigit() or not (1 <= int(token) <= len(self._library_entries)):
                error_widget.update(f"Numero invalide : {token!r}.")
                return
            paths.append(self._library_entries[int(token) - 1].path)

        result = create_favorite(
            self._container.build_log_favorite_repository(), name=name, paths=paths, viewer=ViewerType(viewer_value),
        )
        if not result.success:
            error_widget.update(result.message)
            return

        error_widget.update("")
        self.app.notify(result.message)
        self.query_one("#selection-input", Input).value = ""
        self.query_one("#name-input", Input).value = ""
        self._refresh_favorites()
