"""Ecran Restaurer une archive de log (plan interface §3.4/§8) -
`ArchiveStore.extract_archive`, port direct."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore


class RestoreLogArchiveScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._archive_store: ArchiveStore | None = None
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("RESTAURER UNE ARCHIVE DE LOG", classes="omega-title")
            yield Static("", id="restore-error", classes="omega-hint")
            yield DataTable(id="archives-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Restaurer", id="restore", variant="primary", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#archives-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Archive", "Taille (octets)", "Modifiee le")
        self._refresh()

    def _archive_base_dir(self) -> Path:
        return self._container.project_root / "var" / "backups" / "logs"

    def _refresh(self) -> None:
        self._archive_store = self._container.build_archive_store(self._archive_base_dir())
        table = self.query_one("#archives-table", DataTable)
        table.clear()
        for path in self._archive_store.list_archives():
            info = self._archive_store.get_archive_info(path)
            table.add_row(info["name"], str(info["size_bytes"]), info["modified_at"], key=info["name"])
        self._selected_name = None
        self.query_one("#restore", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_name = str(event.row_key.value)
        self.query_one("#restore", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "restore":
            self._restore()

    def _restore(self) -> None:
        error_widget = self.query_one("#restore-error", Static)
        if self._selected_name is None or self._archive_store is None:
            return
        archive_path = self._archive_store.base_dir / self._selected_name
        dest_dir = self._container.project_root / "var" / "log" / "restored" / self._selected_name.removesuffix(".tar.gz")
        try:
            self._archive_store.extract_archive(archive_path, dest_dir)
        except ArchiveStoreError as exc:
            error_widget.update(f"Erreur : {exc}")
            return
        error_widget.update("")
        self.app.notify(f"Archive restauree dans {dest_dir}")
