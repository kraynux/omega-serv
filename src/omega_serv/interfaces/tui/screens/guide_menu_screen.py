"""Menu Guide navigable (plan guide d'aide §3.6) - parcours lineaire de
toute l'application, miroir de la navigation reelle
(interfaces/tui/guide/menu_tree.py). Distinct de l'aide contextuelle
(touche `?`, _base.py::action_show_help) : celle-ci ouvre directement la
fiche de l'ecran courant, ce menu permet de PARCOURIR le guide comme un
document meme sans etre sur l'ecran concerne."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Select, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.menu_tree import GUIDE_MENU_ENTRIES
from omega_serv.interfaces.tui.guide.registry import ALL_FAQ_ENTRIES, SCREEN_GUIDES
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._export_worker import run_html_export
from omega_serv.interfaces.tui.screens.faq_screen import FaqScreen
from omega_serv.interfaces.tui.screens.guide_detail_screen import GuideDetailScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _export_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class GuideMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("GUIDE D'AIDE"), classes="omega-title")
            yield Static(
                _("Parcourt l'ensemble des écrans d'OMEGA-SERV. Depuis n'importe quel écran "
                "réel, la touche '?' ouvre directement sa fiche."),
                classes="omega-hint",
            )
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("FAQ"), id="faq", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter le guide en HTML"), id="export-html")
            yield Select(
                [(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME, id="export-theme-select",
            )
            yield DataTable(id="guide-menu-table")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#guide-menu-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Section"), _("Écran"), _("Documenté"))
        for index, entry in enumerate(GUIDE_MENU_ENTRIES):
            documented = _("Oui") if entry.screen_class_name in SCREEN_GUIDES else _("À venir")
            table.add_row(entry.section, entry.title, documented, key=str(index))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        entry = GUIDE_MENU_ENTRIES[int(str(event.row_key.value))]
        guide = SCREEN_GUIDES.get(entry.screen_class_name)
        if guide is None:
            self.app.notify(
                _("'{title}' n'est pas encore documenté - à venir dans une prochaine phase.").format(title=entry.title),
                severity="warning",
            )
            return
        self.app.push_screen(GuideDetailScreen(guide))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "faq":
            self.app.push_screen(FaqScreen())
        elif event.button.id == "export-html":
            self._export_html()

    def _exports_dir(self) -> Path:
        override = self._container.settings_store.get("exports_dir_override", "")
        return Path(override) if override else self._container.default_exports_dir

    def _export_html(self) -> None:
        theme_name = str(self.query_one("#export-theme-select", Select).value)
        ordered_guides = [
            asdict(SCREEN_GUIDES[entry.screen_class_name])
            for entry in GUIDE_MENU_ENTRIES
            if entry.screen_class_name in SCREEN_GUIDES
        ]
        faq_entries = [asdict(entry) for entry in ALL_FAQ_ENTRIES]
        run_html_export(
            self, self._container,
            lambda: self._container.export_guide_html(ordered_guides, faq_entries, theme_name),
            self._write_export,
            lambda reason: self.app.notify(reason, severity="error"),
        )

    def _write_export(self, content: str) -> None:
        export_path = self._exports_dir() / f"guide-export.{_export_timestamp()}.html"
        self._container.filesystem.make_directory(export_path.parent)
        self._container.filesystem.write_text(export_path, content)
        self.app.notify(_("Export écrit : {export_path}").format(export_path=export_path))
