# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Cache (plan interface §7, `option enable cache` + regles
par zone/extension) - CRUD sur `settings["zones"]` (path_prefix/
cache_control) et `settings["extensions"]` (extension/cache_control),
plus la valeur `default` (domain/routing/cache_policy.py)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_DEFAULT_CACHE_CONTROL = "no-cache, must-revalidate"


class CacheScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_zone_index: int | None = None
        self._selected_extension: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("CACHE", classes="omega-title")
            yield Static(
                "L'activation de l'option 'cache' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield Static(
                "Valeur par defaut (Cache-Control) - directives usuelles : "
                "no-cache, no-store, must-revalidate, private, public, max-age=<secondes>, immutable "
                "(combinables par virgule, ex: \"no-store, no-cache, must-revalidate\" pour une zone "
                "sensible, \"public, max-age=31536000, immutable\" pour un asset versionne)",
                classes="omega-subtitle",
            )
            yield Input(id="default-input")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Enregistrer la valeur par defaut", id="save-default", variant="primary")

            yield Static("Regles par zone", classes="omega-subtitle")
            yield DataTable(id="zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter une zone", id="add-zone", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer la zone", id="delete-zone", variant="error", disabled=True)

            yield Static("Regles par extension", classes="omega-subtitle")
            yield DataTable(id="extensions-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter une extension", id="add-extension", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer l'extension", id="delete-extension", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        zones_table = self.query_one("#zones-table", DataTable)
        zones_table.cursor_type = "row"
        zones_table.add_columns("Prefixe", "Cache-Control")
        extensions_table = self.query_one("#extensions-table", DataTable)
        extensions_table.cursor_type = "row"
        extensions_table.add_columns("Extension", "Cache-Control")
        self._refresh()

    def _settings(self) -> dict:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return {}
        option = result.config.options.get("cache")
        return dict(option.settings) if option is not None else {}

    def _refresh(self) -> None:
        settings = self._settings()
        self.query_one("#default-input", Input).value = settings.get("default", _DEFAULT_CACHE_CONTROL)

        zones_table = self.query_one("#zones-table", DataTable)
        zones_table.clear()
        for index, zone in enumerate(settings.get("zones", [])):
            zones_table.add_row(zone.get("path_prefix", ""), zone.get("cache_control", ""), key=str(index))
        self._selected_zone_index = None
        self.query_one("#delete-zone", Button).disabled = True

        extensions_table = self.query_one("#extensions-table", DataTable)
        extensions_table.clear()
        for extension, cache_control in sorted(settings.get("extensions", {}).items()):
            extensions_table.add_row(extension, cache_control, key=extension)
        self._selected_extension = None
        self.query_one("#delete-extension", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "zones-table":
            self._selected_zone_index = int(str(event.row_key.value))
            self.query_one("#delete-zone", Button).disabled = False
        elif event.data_table.id == "extensions-table":
            self._selected_extension = str(event.row_key.value)
            self.query_one("#delete-extension", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "save-default":
            self._save_settings(default=self.query_one("#default-input", Input).value.strip() or _DEFAULT_CACHE_CONTROL)
            return
        if button_id == "add-zone":
            self.app.push_screen(
                DynamicFormScreen(
                    title="AJOUTER UNE REGLE DE ZONE",
                    fields=[
                        ("path_prefix", "Prefixe (ex: /static/)", ""),
                        ("cache_control", "Cache-Control (ex: no-cache, no-store, must-revalidate, private, public, max-age=<s>, immutable)", ""),
                    ],
                ),
                self._add_zone,
            )
            return
        if button_id == "delete-zone" and self._selected_zone_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA REGLE", message="Confirmer la suppression de cette regle de zone ?"),
                self._delete_zone,
            )
            return
        if button_id == "add-extension":
            self.app.push_screen(
                DynamicFormScreen(
                    title="AJOUTER UNE REGLE D'EXTENSION",
                    fields=[
                        ("extension", "Extension (ex: .css)", ""),
                        ("cache_control", "Cache-Control (ex: no-cache, no-store, must-revalidate, private, public, max-age=<s>, immutable)", ""),
                    ],
                ),
                self._add_extension,
            )
            return
        if button_id == "delete-extension" and self._selected_extension is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA REGLE", message="Confirmer la suppression de cette regle d'extension ?"),
                self._delete_extension,
            )

    def _add_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        path_prefix = values["path_prefix"].strip()
        if not path_prefix.startswith("/"):
            self.query_one("#form-error", Static).update(f"Le prefixe doit commencer par '/' : {path_prefix!r}")
            return
        zones = list(self._settings().get("zones", []))
        zones.append({"path_prefix": path_prefix, "cache_control": values["cache_control"].strip()})
        self._save_settings(zones=zones)

    def _delete_zone(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_zone_index is None:
            return
        zones = list(self._settings().get("zones", []))
        del zones[self._selected_zone_index]
        self._save_settings(zones=zones)

    def _add_extension(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        extension = values["extension"].strip()
        if not extension.startswith("."):
            self.query_one("#form-error", Static).update(f"L'extension doit commencer par '.' : {extension!r}")
            return
        extensions = dict(self._settings().get("extensions", {}))
        extensions[extension] = values["cache_control"].strip()
        self._save_settings(extensions=extensions)

    def _delete_extension(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_extension is None:
            return
        extensions = dict(self._settings().get("extensions", {}))
        extensions.pop(self._selected_extension, None)
        self._save_settings(extensions=extensions)

    def _save_settings(self, **updates: object) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("cache")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings.update(updates)
        new_options = dict(load_result.config.options)
        new_options["cache"] = Option(name="cache", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh()
        notify_reload_required(self, self._container, "Regles de cache mises a jour.")
