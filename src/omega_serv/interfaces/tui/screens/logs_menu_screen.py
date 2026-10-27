"""Ecran Gestion des logs (plan interface §8, menu 4) - REFONDU en deux
colonnes (2026-10-15, au meme niveau qu'omega-log - OMEGA-LOG_PLAN
§7) : colonne 1 "Bibliotheque" (Bibliotheque/Favoris/Voir les logs/
Voir et traiter IP, portes depuis omega-log), colonne 2 "Maintenance"
(Rotate/Restaurer/Purger/Exporter, deja existants, inchanges). Meme
patron CSS que `active_defense_menu_screen.py` (`.omega-panel-row` + 2x
`.omega-home-menu`, chacun son `border_title`).

"Statistiques du log d'acces" (ancien `LogStatsScreen`) et "Top IPs"
(ancien `TopIpsScreen`, desormais `ProcessIpScreen`) ne sont PLUS des
boutons separes - leurs besoins sont desormais couverts par "Voir les
logs" (Viewer Simple, stats generiques sur n'importe quel log) et "Voir
et traiter IP" (generalise a toute la Bibliotheque) respectivement.
`LogStatsScreen` reste present dans le code (fonctionnel, non
supprime) mais n'est plus relie a ce menu - son besoin specifique
(repartition HTTP detaillee sur l'access log, export 5 themes) reste a
rouvrir separement si un besoin reel se confirme, jamais une
suppression silencieuse de code qui marche."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.export_log_archives_screen import ExportLogArchivesScreen
from omega_serv.interfaces.tui.screens.log_favorites_screen import LogFavoritesScreen
from omega_serv.interfaces.tui.screens.log_library_screen import LogLibraryScreen
from omega_serv.interfaces.tui.screens.log_rotation_screen import LogRotationScreen
from omega_serv.interfaces.tui.screens.log_view_screen import LogViewScreen
from omega_serv.interfaces.tui.screens.process_ip_screen import ProcessIpScreen
from omega_serv.interfaces.tui.screens.purge_log_archives_screen import PurgeLogArchivesScreen
from omega_serv.interfaces.tui.screens.restore_log_archive_screen import RestoreLogArchiveScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_LIBRARY_ITEMS: tuple[tuple[str, str], ...] = (
    ("library", _("Bibliothèque")),
    ("favorites", _("Favoris")),
    ("view-logs", _("Voir les logs")),
    ("process-ip", _("Voir et traiter IP")),
)
_MAINTENANCE_ITEMS: tuple[tuple[str, str], ...] = (
    ("rotation", _("Rotate / archivage")),
    ("restore", _("Restaurer une archive")),
    ("purge", _("Purger les archives")),
    ("export", _("Exporter")),
)


class LogsMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            with Center():
                yield Static(_("GESTION DES LOGS"), classes="omega-title")
            with Center(), Horizontal(classes="omega-panel-row"):
                with Vertical(classes="omega-home-menu") as library_menu:
                    for item_id, label in _LIBRARY_ITEMS:
                        with Container(classes="omega-btn-frame"):
                            yield Button(label, id=item_id)
                    library_menu.border_title = _("BIBLIOTHÈQUE")
                with Vertical(classes="omega-home-menu") as maintenance_menu:
                    for item_id, label in _MAINTENANCE_ITEMS:
                        with Container(classes="omega-btn-frame"):
                            yield Button(label, id=item_id)
                    maintenance_menu.border_title = _("MAINTENANCE")
            with Center(), Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        screen = self._screen_for(event.button.id)
        if screen is not None:
            self.app.push_screen(screen)

    def _screen_for(self, item_id: str | None) -> Screen[None] | None:
        mapping = {
            "library": LogLibraryScreen,
            "favorites": LogFavoritesScreen,
            "view-logs": LogViewScreen,
            "process-ip": ProcessIpScreen,
            "rotation": LogRotationScreen,
            "restore": RestoreLogArchiveScreen,
            "purge": PurgeLogArchivesScreen,
            "export": ExportLogArchivesScreen,
        }
        screen_cls = mapping.get(item_id) if item_id else None
        if screen_cls is None:
            return None
        return screen_cls(container=self._container)
