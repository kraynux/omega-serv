# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Alias (plan interface §7, `option enable aliases` + liste) -
CRUD complet sur `options["aliases"].settings["list"]` (domain/routing/
alias.py::AliasRule). L'activation/desactivation de l'option elle-meme
reste le role de l'ecran Options (menu 2) - ce sous-ecran ne touche que
le contenu de la liste, jamais `enabled`."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.alias import AliasRule, parse_alias_rules, validate_alias_rule
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class AliasesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ALIAS", classes="omega-title")
            yield Static(
                "L'activation de l'option 'aliases' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="aliases-table")
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
        table = self.query_one("#aliases-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Prefixe URL", "Cible", "Hors webroot")
        self._refresh_table()

    def _rules(self) -> list[AliasRule]:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return []
        settings = result.config.options.get("aliases")
        if settings is None:
            return []
        return parse_alias_rules(settings.settings.get("list", []))

    def _refresh_table(self) -> None:
        table = self.query_one("#aliases-table", DataTable)
        table.clear()
        for index, rule in enumerate(self._rules()):
            table.add_row(rule.url_prefix, rule.target_path, "oui" if rule.allow_outside_webroot else "non", key=str(index))
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
                    title="AJOUTER UN ALIAS",
                    fields=[
                        ("url_prefix", "Prefixe URL (ex: /media/)", ""),
                        ("target_path", "Chemin cible (ex: webroot/media)", ""),
                        ("allow_outside_webroot", "Autoriser hors webroot (oui/non)", "non"),
                    ],
                ),
                self._add_rule,
            )
            return
        if event.button.id == "edit" and self._selected_index is not None:
            rules = self._rules()
            rule = rules[self._selected_index]
            self.app.push_screen(
                DynamicFormScreen(
                    title="MODIFIER L'ALIAS",
                    fields=[
                        ("url_prefix", "Prefixe URL", rule.url_prefix),
                        ("target_path", "Chemin cible", rule.target_path),
                        ("allow_outside_webroot", "Autoriser hors webroot (oui/non)", "oui" if rule.allow_outside_webroot else "non"),
                    ],
                ),
                self._edit_rule,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER L'ALIAS", message="Confirmer la suppression de cet alias ?"),
                self._delete_rule,
            )

    def _add_rule(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        rule = AliasRule(
            url_prefix=values["url_prefix"],
            target_path=values["target_path"],
            allow_outside_webroot=values["allow_outside_webroot"].strip().lower() in ("oui", "true", "1", "o", "y"),
        )
        error = validate_alias_rule(rule)
        if error is not None:
            self.query_one("#form-error", Static).update(f"Erreur : {error}")
            return
        rules = self._rules()
        rules.append(rule)
        self._save_rules(rules)

    def _edit_rule(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        rule = AliasRule(
            url_prefix=values["url_prefix"],
            target_path=values["target_path"],
            allow_outside_webroot=values["allow_outside_webroot"].strip().lower() in ("oui", "true", "1", "o", "y"),
        )
        error = validate_alias_rule(rule)
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

    def _save_rules(self, rules: list[AliasRule]) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("aliases")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["list"] = [
            {"url_prefix": r.url_prefix, "target_path": r.target_path, "allow_outside_webroot": r.allow_outside_webroot}
            for r in rules
        ]
        new_options = dict(load_result.config.options)
        new_options["aliases"] = Option(name="aliases", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_reload_required(self, self._container, "Liste des alias mise a jour.")
