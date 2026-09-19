"""Sous-ecran Redirections (plan interface §7, `option enable redirects`
+ liste) - CRUD complet sur `options["redirects"].settings["list"]`
(domain/routing/redirect.py::RedirectRule). Meme separation que
aliases_screen.py : l'activation de l'option reste le role de l'ecran
Options."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.redirect import (
    RedirectRule,
    parse_redirect_rules,
    validate_redirect_rule,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class RedirectsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("REDIRECTIONS", classes="omega-title")
            yield Static(
                "L'activation de l'option 'redirects' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="redirects-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Modifier", id="edit", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#redirects-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Prefixe URL", "Destination", "Code")
        self._refresh_table()

    def _rules(self) -> list[RedirectRule]:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return []
        option = result.config.options.get("redirects")
        if option is None:
            return []
        return parse_redirect_rules(option.settings.get("list", []))

    def _refresh_table(self) -> None:
        table = self.query_one("#redirects-table", DataTable)
        table.clear()
        for index, rule in enumerate(self._rules()):
            table.add_row(rule.url_prefix, rule.destination, str(rule.status_code), key=str(index))
        self._selected_index = None
        self.query_one("#edit", Button).disabled = True
        self.query_one("#delete", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#edit", Button).disabled = False
        self.query_one("#delete", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "add":
            self.app.push_screen(
                DynamicFormScreen(
                    title="AJOUTER UNE REDIRECTION",
                    fields=[
                        ("url_prefix", "Prefixe URL (ex: /old/)", ""),
                        ("destination", "Destination (ex: /new/)", ""),
                        ("status_code", "Code (301/302/307/308)", "302"),
                    ],
                ),
                self._add_rule,
            )
            return
        if event.button.id == "edit" and self._selected_index is not None:
            rule = self._rules()[self._selected_index]
            self.app.push_screen(
                DynamicFormScreen(
                    title="MODIFIER LA REDIRECTION",
                    fields=[
                        ("url_prefix", "Prefixe URL", rule.url_prefix),
                        ("destination", "Destination", rule.destination),
                        ("status_code", "Code (301/302/307/308)", str(rule.status_code)),
                    ],
                ),
                self._edit_rule,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA REDIRECTION", message="Confirmer la suppression de cette redirection ?"),
                self._delete_rule,
            )

    def _build_rule(self, values: dict[str, str]) -> RedirectRule | None:
        status_text = values["status_code"].strip()
        try:
            status_code = int(status_text)
        except ValueError:
            self.query_one("#form-error", Static).update(f"Code invalide (nombre attendu) : {status_text!r}")
            return None
        return RedirectRule(url_prefix=values["url_prefix"], destination=values["destination"], status_code=status_code)

    def _add_rule(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        rule = self._build_rule(values)
        if rule is None:
            return
        error = validate_redirect_rule(rule)
        if error is not None:
            self.query_one("#form-error", Static).update(f"Erreur : {error}")
            return
        rules = self._rules()
        rules.append(rule)
        self._save_rules(rules)

    def _edit_rule(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        rule = self._build_rule(values)
        if rule is None:
            return
        error = validate_redirect_rule(rule)
        if error is not None:
            self.query_one("#form-error", Static).update(f"Erreur : {error}")
            return
        rules = self._rules()
        rules[self._selected_index] = rule
        self._save_rules(rules)

    def _delete_rule(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        rules = self._rules()
        del rules[self._selected_index]
        self._save_rules(rules)

    def _save_rules(self, rules: list[RedirectRule]) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("redirects")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["list"] = [
            {"url_prefix": r.url_prefix, "destination": r.destination, "status_code": r.status_code} for r in rules
        ]
        new_options = dict(load_result.config.options)
        new_options["redirects"] = Option(name="redirects", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_reload_required(self, self._container, "Liste des redirections mise a jour.")
