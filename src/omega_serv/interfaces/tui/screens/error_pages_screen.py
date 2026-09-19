"""Sous-ecran Pages d'erreur (plan interface §7, retour utilisateur
2026-09-09 : "on mettra des pages html d'erreur fournies de base") -
les pages HTML par defaut sont toujours servies (aucun toggle ne les
desactive, voir domain/http/error_pages.py) ; l'option "error_pages"
ne controle ici que la surcharge personnalisee (repertoire contenant
des fichiers `{code}.html`, active dans le menu Options).

Meme patron minimal que cache_screen.py (settings-only, pas de CRUD) -
liste en plus les codes de statut connus (domain/http/status_codes.py)
avec l'etat "Personnalisee" (Oui/Non) pour montrer immediatement quels
fichiers sont deja fournis dans le repertoire configure, sans obliger
l'utilisateur a aller verifier sur le disque."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_DEFAULT_CUSTOM_DIR = "webroot/.errors"

_KNOWN_ERROR_STATUSES: tuple[HttpStatus, ...] = tuple(
    sorted((s for s in HttpStatus if s >= 400), key=int)
)


class ErrorPagesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("PAGES D'ERREUR", classes="omega-title")
            yield Static(
                "Des pages HTML par defaut sont toujours servies pour toute reponse "
                "d'erreur (404, 403, 500...) sans corps - aucune activation requise. "
                "L'option 'error_pages' (menu Options) ne controle que la surcharge "
                "personnalisee ci-dessous : un fichier <statut>.html dans le "
                "repertoire configure remplace la page par defaut pour ce statut.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("", id="enabled-state", classes="omega-hint")
            yield Static(
                "Repertoire de surcharge (relatif a la racine du projet, "
                "fichiers nommes <statut>.html, ex: 404.html)",
                classes="omega-subtitle",
            )
            yield Input(id="dir-input")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Enregistrer", id="save", variant="primary")

            yield Static("Statuts geres", classes="omega-subtitle")
            yield DataTable(id="statuses-table")

            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#statuses-table", DataTable)
        table.add_columns("Statut", "Raison", "Personnalisee")
        self._refresh()

    def _settings(self) -> dict:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return {}
        option = result.config.options.get("error_pages")
        return dict(option.settings) if option is not None else {}

    def _is_enabled(self) -> bool:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return False
        option = result.config.options.get("error_pages")
        return option is not None and option.enabled

    def _refresh(self) -> None:
        state = self.query_one("#enabled-state", Static)
        if self._is_enabled():
            state.update("Etat : ACTIVEE - la surcharge personnalisee est appliquee.")
        else:
            state.update(
                "Etat : DESACTIVEE - ce repertoire est configure mais SANS EFFET tant que "
                "l'option n'est pas activee depuis le menu Options (selectionner 'error_pages' -> Activer)."
            )

        custom_dir_value = self._settings().get("custom_dir", _DEFAULT_CUSTOM_DIR)
        self.query_one("#dir-input", Input).value = str(custom_dir_value)

        custom_dir = self._container.project_root / str(custom_dir_value)
        table = self.query_one("#statuses-table", DataTable)
        table.clear()
        for status in _KNOWN_ERROR_STATUSES:
            candidate = custom_dir / f"{int(status)}.html"
            personnalisee = "Oui" if self._container.filesystem.is_file(candidate) else "Non"
            table.add_row(str(int(status)), status.reason_phrase, personnalisee, key=str(int(status)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._save(self.query_one("#dir-input", Input).value.strip() or _DEFAULT_CUSTOM_DIR)

    def _save(self, custom_dir: str) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("error_pages")
        enabled = existing.enabled if existing is not None else False
        new_options = dict(load_result.config.options)
        new_options["error_pages"] = Option(name="error_pages", enabled=enabled, settings={"custom_dir": custom_dir})
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh()
        if enabled:
            notify_reload_required(self, self._container, "Repertoire de surcharge mis a jour.")
        else:
            self.app.notify(
                "Repertoire de surcharge mis a jour - MAIS l'option est desactivee : "
                "sans effet tant que vous ne l'activez pas depuis Options.",
                severity="warning",
                timeout=10,
            )
