"""Ecran Purger les archives de logs (plan interface §3.4/§8) -
`ArchiveStore.delete_archive`, meme table que `restore_log_archive_screen.py`
mais action destructive donc confirmation obligatoire (meme patron que
`revoke_certificate_screen.py`)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore


class PurgeLogArchivesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._archive_store: ArchiveStore | None = None
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("PURGER LES ARCHIVES DE LOGS", classes="omega-title")
            yield Static("", id="purge-error", classes="omega-hint")
            yield DataTable(id="archives-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="purge", variant="error", disabled=True)
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
        self.query_one("#purge", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_name = str(event.row_key.value)
        self.query_one("#purge", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "purge" and self._selected_name is not None:
            self.app.push_screen(
                ConfirmScreen(
                    title="SUPPRIMER L'ARCHIVE",
                    message=f"Supprimer definitivement {self._selected_name} ?",
                ),
                self._purge_if_confirmed,
            )

    def _purge_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_name is None or self._archive_store is None:
            return
        archive_path = self._archive_store.base_dir / self._selected_name
        deleted = self._archive_store.delete_archive(archive_path)
        error_widget = self.query_one("#purge-error", Static)
        if not deleted:
            error_widget.update(f"Archive introuvable : {self._selected_name}")
        else:
            error_widget.update("")
            self.app.notify(f"Archive supprimee : {self._selected_name}")
        self._refresh()
