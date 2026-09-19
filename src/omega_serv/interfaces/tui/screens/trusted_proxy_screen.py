"""Sous-ecran Proxies de confiance (plan interface §7, `option enable
trusted_proxy` + reseaux/en-tete preferee) - CRUD sur
`settings["trusted_networks"]` (domain/security/trusted_proxy.py,
verification CIDR reelle via ipaddress au clic) ; `header_preference`
reste un champ texte ordonne simple (l'ordre de preference des en-tetes
compte, une liste CRUD non ordonnable n'apporterait rien ici)."""
from __future__ import annotations

import ipaddress
from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_DEFAULT_HEADER_PREFERENCE = ("Forwarded", "X-Forwarded-For")


class TrustedProxyScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("PROXIES DE CONFIANCE", classes="omega-title")
            yield Static(
                "L'activation de l'option 'trusted_proxy' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("Reseaux de confiance (CIDR)", classes="omega-subtitle")
            yield DataTable(id="networks-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete", variant="error", disabled=True)
            yield Static("En-tetes preferes (ordre, separes par des virgules)", classes="omega-subtitle")
            yield Input(id="header-preference-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Enregistrer les en-tetes", id="save-headers", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#networks-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Reseau")
        self._refresh_table()

    def _settings(self) -> dict:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return {}
        option = result.config.options.get("trusted_proxy")
        return dict(option.settings) if option is not None else {}

    def _refresh_table(self) -> None:
        table = self.query_one("#networks-table", DataTable)
        table.clear()
        networks = self._settings().get("trusted_networks", [])
        for index, network in enumerate(networks):
            table.add_row(network, key=str(index))
        self._selected_index = None
        self.query_one("#delete", Button).disabled = True
        header_preference = self._settings().get("header_preference", list(_DEFAULT_HEADER_PREFERENCE))
        self.query_one("#header-preference-input", Input).value = ", ".join(header_preference)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#delete", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "add":
            self.app.push_screen(
                DynamicFormScreen(title="AJOUTER UN RESEAU", fields=[("network", "Reseau CIDR (ex: 10.0.0.0/8)", "")]),
                self._add_network,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LE RESEAU", message="Confirmer la suppression de ce reseau ?"),
                self._delete_network,
            )
            return
        if event.button.id == "save-headers":
            self._save_header_preference()

    def _add_network(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        network_text = values["network"].strip()
        try:
            ipaddress.ip_network(network_text, strict=False)
        except ValueError:
            self.query_one("#form-error", Static).update(f"Reseau CIDR invalide : {network_text!r}")
            return
        settings = self._settings()
        networks = list(settings.get("trusted_networks", []))
        networks.append(network_text)
        self._save_settings(trusted_networks=networks)

    def _delete_network(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        settings = self._settings()
        networks = list(settings.get("trusted_networks", []))
        del networks[self._selected_index]
        self._save_settings(trusted_networks=networks)

    def _save_header_preference(self) -> None:
        headers = [
            item.strip() for item in self.query_one("#header-preference-input", Input).value.split(",") if item.strip()
        ]
        if not headers:
            self.query_one("#form-error", Static).update("La liste des en-tetes ne peut pas etre vide.")
            return
        self._save_settings(header_preference=headers)

    def _save_settings(self, **updates: object) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("trusted_proxy")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings.update(updates)
        new_options = dict(load_result.config.options)
        new_options["trusted_proxy"] = Option(name="trusted_proxy", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_reload_required(self, self._container, "Proxies de confiance mis a jour.")
