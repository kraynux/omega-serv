# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Exporter la liste des archives de logs (plan interface §3.4/§8) -
meme patron JSON/HTML que `capabilities_screen.py`, applique aux metadonnees
d'archives (`ArchiveStore.get_archive_info`) plutot qu'aux capacites.
Export HTML via jinja2 (infrastructure/exporters/html_exporter.py,
retour utilisateur 2026-09-09) - meme mecanisme et memes 5 themes que le
reste de la suite."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Select, Static

from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _export_timestamp() -> str:
    # Meme format que domain/logs/rotation.py::generate_archive_name
    # (retour utilisateur 2026-09-09 : ces exports ecrasaient
    # silencieusement le precedent, faute d'horodatage dans le nom).
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class ExportLogArchivesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._infos: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("EXPORTER LA LISTE DES ARCHIVES", classes="omega-title")
            yield Static("", id="export-error", classes="omega-hint")
            yield DataTable(id="archives-table")
            yield Static("Theme d'export HTML", classes="omega-subtitle")
            yield Select(
                [(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME, id="export-theme-select",
            )
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Rafraichir", id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Exporter JSON", id="export-json")
                with Container(classes="omega-btn-frame"):
                    yield Button("Exporter HTML", id="export-html")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#archives-table", DataTable)
        table.add_columns("Archive", "Taille (octets)", "Modifiee le")
        self._refresh()

    def _archive_base_dir(self) -> Path:
        return self._container.project_root / "var" / "backups" / "logs"

    def _refresh(self) -> None:
        archive_store = self._container.build_archive_store(self._archive_base_dir())
        self._infos = [archive_store.get_archive_info(p) for p in archive_store.list_archives()]
        table = self.query_one("#archives-table", DataTable)
        table.clear()
        for info in self._infos:
            table.add_row(info["name"], str(info["size_bytes"]), info["modified_at"], key=info["name"])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "refresh":
            self._refresh()
            return
        if button_id == "export-json":
            self._export_json()
            return
        if button_id == "export-html":
            self._export_html()

    def _exports_dir(self) -> Path:
        # Respecte la surcharge configuree dans l'ecran Reglages
        # (parametre "exports_dir_override", touche 'o') - meme mecanisme
        # que app.py::_deliver_screenshot_to_configured_dir pour les captures.
        override = self._container.settings_store.get("exports_dir_override", "")
        return Path(override) if override else self._container.default_exports_dir

    def _export_json(self) -> None:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "archives": self._infos,
        }
        content = json.dumps(payload, indent=2, ensure_ascii=False)
        export_path = self._exports_dir() / f"log-archives-export.{_export_timestamp()}.json"
        self._write_export(export_path, content)

    def _export_html(self) -> None:
        theme_name = str(self.query_one("#export-theme-select", Select).value)
        content = self._container.export_log_archives_html(self._infos, theme_name)
        if content is None:
            self.query_one("#export-error", Static).update("Export HTML indisponible dans cet environnement.")
            return
        export_path = self._exports_dir() / f"log-archives-export.{_export_timestamp()}.html"
        self._write_export(export_path, content)

    def _write_export(self, export_path: Path, content: str) -> None:
        self._container.filesystem.make_directory(export_path.parent)
        self._container.filesystem.write_text(export_path, content)
        self.app.notify(f"Export ecrit : {export_path}")
