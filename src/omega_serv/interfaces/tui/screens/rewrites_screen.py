# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Rewrites (plan interface §7, `option enable rewrites` +
liste) - CRUD complet sur `options["rewrites"].settings["list"]`
(domain/routing/rewrite.py::RewriteRule). Pas de `validate_rewrite_rule`
domain existant (seulement `parse_rewrite_rules`/`apply_rewrites`) -
validation minimale locale (prefixes non vides, `match_prefix` commence
par '/'), meme regle que aliases/redirects sans dupliquer une fonction
qui n'existe pas encore ailleurs."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.rewrite import RewriteRule, parse_rewrite_rules
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _validate_rewrite_rule(rule: RewriteRule) -> str | None:
    if not rule.match_prefix.startswith("/"):
        return f"match_prefix doit commencer par '/' : {rule.match_prefix!r}"
    if not rule.replacement_prefix:
        return "replacement_prefix ne peut pas etre vide"
    return None


class RewritesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("REWRITES", classes="omega-title")
            yield Static(
                "L'activation de l'option 'rewrites' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="rewrites-table")
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
        table = self.query_one("#rewrites-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Prefixe recherche", "Prefixe remplacement")
        self._refresh_table()

    def _rules(self) -> list[RewriteRule]:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return []
        option = result.config.options.get("rewrites")
        if option is None:
            return []
        return parse_rewrite_rules(option.settings.get("list", []))

    def _refresh_table(self) -> None:
        table = self.query_one("#rewrites-table", DataTable)
        table.clear()
        for index, rule in enumerate(self._rules()):
            table.add_row(rule.match_prefix, rule.replacement_prefix, key=str(index))
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
                    title="AJOUTER UN REWRITE",
                    fields=[
                        ("match_prefix", "Prefixe recherche (ex: /old/)", ""),
                        ("replacement_prefix", "Prefixe remplacement (ex: /new/)", ""),
                    ],
                ),
                self._add_rule,
            )
            return
        if event.button.id == "edit" and self._selected_index is not None:
            rule = self._rules()[self._selected_index]
            self.app.push_screen(
                DynamicFormScreen(
                    title="MODIFIER LE REWRITE",
                    fields=[
                        ("match_prefix", "Prefixe recherche", rule.match_prefix),
                        ("replacement_prefix", "Prefixe remplacement", rule.replacement_prefix),
                    ],
                ),
                self._edit_rule,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LE REWRITE", message="Confirmer la suppression de ce rewrite ?"),
                self._delete_rule,
            )

    def _add_rule(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        rule = RewriteRule(match_prefix=values["match_prefix"], replacement_prefix=values["replacement_prefix"])
        error = _validate_rewrite_rule(rule)
        if error is not None:
            self.query_one("#form-error", Static).update(f"Erreur : {error}")
            return
        rules = self._rules()
        rules.append(rule)
        self._save_rules(rules)

    def _edit_rule(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        rule = RewriteRule(match_prefix=values["match_prefix"], replacement_prefix=values["replacement_prefix"])
        error = _validate_rewrite_rule(rule)
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

    def _save_rules(self, rules: list[RewriteRule]) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("rewrites")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["list"] = [
            {"match_prefix": r.match_prefix, "replacement_prefix": r.replacement_prefix} for r in rules
        ]
        new_options = dict(load_result.config.options)
        new_options["rewrites"] = Option(name="rewrites", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_reload_required(self, self._container, "Liste des rewrites mise a jour.")
