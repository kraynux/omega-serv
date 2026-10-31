"""Ecran Bibliotheque (gestion des logs, refonte menu 2026-10-15,
OMEGA-LOG_PLAN §3/§10) - hub central referencant les logs a traiter,
alimentation MANUELLE pour cette passe (un scan automatique du type
"Registre" d'omega-log est explicitement differe, YAGNI tant qu'aucun
besoin reel confirme).

Bouton "Ajouter les logs connus d'Omega-Serv" AJOUTE (sans equivalent
chez omega-log, qui n'a pas de logs "a lui") : convenience SCOPEE
(seulement les quelques logs deja connus de ce projet - access/error/
waf-alerts, + magnet si actif - jamais un scan du systeme) pour ne pas
perdre l'acces en un clic qu'offrait l'ancien `LogViewerScreen` a ses
propres logs, maintenant que cet ecran ne les propose plus directement
(voir sa propre docstring) - reste une action EXPLICITE de l'utilisateur,
jamais un ajout automatique en arriere-plan."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.logs.library import (
    add_to_library,
    list_library,
    remove_from_library,
)
from omega_serv.core.i18n import _
from omega_serv.domain.logs.library import LogFile
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.remote_log_sources_screen import RemoteLogSourcesScreen
from omega_serv.interfaces.tui.widgets.log_library_table import LogLibraryTable

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_KNOWN_LOG_ATTRS: tuple[str, ...] = ("access", "error", "waf_alerts")


class LogLibraryScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_path: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("BIBLIOTHÈQUE"), classes="omega-title")
            yield Static("", id="library-hint", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                yield Input(placeholder=_("Chemin à ajouter manuellement"), id="path-input")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter"), id="add", variant="primary")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Ajouter les logs connus d'Omega-Serv"), id="add-known")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Sources distantes (SSH)"), id="remote-sources")
            yield LogLibraryTable(id="log-list")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retirer la sélection"), id="remove", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Rafraîchir"), id="refresh")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "log-list":
            return
        row = event.data_table.get_row_at(event.cursor_row)
        self._selected_path = str(row[1]) if row else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
        elif button_id == "refresh":
            self._refresh()
        elif button_id == "add":
            self._add_manual()
        elif button_id == "add-known":
            self._add_known()
        elif button_id == "remote-sources":
            self.app.push_screen(RemoteLogSourcesScreen(container=self._container))
        elif button_id == "remove":
            self._remove_selected()

    def _refresh(self) -> None:
        entries = list_library(self._container.build_log_library_repository())
        self.query_one("#log-list", LogLibraryTable).load(entries)
        stale = sum(1 for e in entries if e.is_stale)
        missing = sum(1 for e in entries if not e.exists)
        self.query_one("#library-hint", Static).update(
            _("{count} log(s) référence(s) - {stale} suspect(s), {missing} introuvable(s) actuellement.").format(count=len(entries), stale=stale, missing=missing)
        )

    def _add_manual(self) -> None:
        path_input = self.query_one("#path-input", Input)
        raw_path = path_input.value.strip()
        if not raw_path:
            self.app.notify(_("Saisissez un chemin."), severity="warning")
            return
        add_to_library(self._container.build_log_library_repository(), LogFile(path=raw_path, access="file"))
        path_input.value = ""
        self._refresh()

    def _magnet_active(self, config: OmegaServConfig) -> bool:
        if "waf" not in config.options or not config.option_enabled("waf"):
            return False
        return parse_waf_config(config.options["waf"].settings).magnet.enabled

    def _add_known(self) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.app.notify(_("Erreur de configuration - impossible d'ajouter."), severity="error")
            return
        config = load_result.config
        repository = self._container.build_log_library_repository()
        added = 0
        for attr in _KNOWN_LOG_ATTRS:
            relative_path = getattr(config.logs, attr, None)
            if relative_path is None:
                continue
            path = self._container.project_root / relative_path
            add_to_library(repository, LogFile(path=str(path), access="file", service_id="omega-serv"))
            added += 1
        if self._magnet_active(config):
            magnet_paths = parse_waf_config(config.options["waf"].settings).magnet.paths
            for relative_path in (magnet_paths.alerts_log, magnet_paths.blocklist_log):
                path = self._container.project_root / relative_path
                add_to_library(repository, LogFile(path=str(path), access="file", service_id="omega-serv-magnet"))
                added += 1
        self.app.notify(_("{added} log(s) connu(s) d'Omega-Serv ajouté(s) (déjà présents remplacés, jamais dupliques).").format(added=added))
        self._refresh()

    def _remove_selected(self) -> None:
        if self._selected_path is None:
            self.app.notify(_("Sélectionnez une ligne dans la liste."), severity="warning")
            return
        path = self._selected_path
        self.app.push_screen(
            ConfirmScreen(title=_("RETIRER DE LA BIBLIOTHÈQUE ?"), message=path),
            lambda confirmed: self._remove_if_confirmed(confirmed, path),
        )

    def _remove_if_confirmed(self, confirmed: bool | None, path: str) -> None:
        if not confirmed:
            return
        remove_from_library(self._container.build_log_library_repository(), path)
        self._selected_path = None
        self._refresh()
