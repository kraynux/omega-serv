# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Gestion des logs (plan interface §8, menu 4) - sous-menu plat
vers les sous-ecrans deja construits. Phase V (2026-09-08) : voir/suivre
un fichier, lnav. Phase VI (2026-09-08) : rotation/archivage, restaurer/
purger une archive, export de la liste des archives, statistiques et top
IPs - tableau §8 complet."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.export_log_archives_screen import ExportLogArchivesScreen
from omega_serv.interfaces.tui.screens.lnav_screen import LnavScreen
from omega_serv.interfaces.tui.screens.log_rotation_screen import LogRotationScreen
from omega_serv.interfaces.tui.screens.log_stats_screen import LogStatsScreen
from omega_serv.interfaces.tui.screens.log_viewer_screen import LogViewerScreen
from omega_serv.interfaces.tui.screens.purge_log_archives_screen import PurgeLogArchivesScreen
from omega_serv.interfaces.tui.screens.restore_log_archive_screen import RestoreLogArchiveScreen
from omega_serv.interfaces.tui.screens.top_ips_screen import TopIpsScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_MENU_ITEMS: tuple[tuple[str, str], ...] = (
    ("viewer", "Voir / suivre un fichier log"),
    ("lnav", "Suivre les logs fusionnes (lnav)"),
    ("rotation", "Rotation / archivage des logs"),
    ("restore", "Restaurer une archive de log"),
    ("purge", "Purger les archives de logs"),
    ("export", "Exporter Archives"),
    ("stats", "Statistiques du log d'acces"),
    ("top-ips", "Top IPs du log d'acces"),
)


class LogsMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            with Center():
                yield Static("GESTION DES LOGS", classes="omega-title")
            with Center(), Vertical(classes="omega-home-menu") as menu:
                for item_id, label in _MENU_ITEMS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
                menu.border_title = "SOUS-ECRANS"
            with Center(), Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        screen = self._screen_for(event.button.id)
        if screen is not None:
            self.app.push_screen(screen)

    def _screen_for(self, item_id: str | None) -> Screen[None] | None:
        if item_id == "viewer":
            return LogViewerScreen(container=self._container)
        if item_id == "lnav":
            return LnavScreen(container=self._container)
        if item_id == "rotation":
            return LogRotationScreen(container=self._container)
        if item_id == "restore":
            return RestoreLogArchiveScreen(container=self._container)
        if item_id == "purge":
            return PurgeLogArchivesScreen(container=self._container)
        if item_id == "export":
            return ExportLogArchivesScreen(container=self._container)
        if item_id == "stats":
            return LogStatsScreen(container=self._container)
        if item_id == "top-ips":
            return TopIpsScreen(container=self._container)
        return None
