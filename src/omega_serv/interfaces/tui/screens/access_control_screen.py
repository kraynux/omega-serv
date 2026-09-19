"""Sous-ecran Controle d'acces (plan interface §7, `option enable
access_control` + liste) - CRUD complet sur
`options["access_control"].settings["list"]` (domain/routing/
access_rule.py::AccessRule). Retour utilisateur 2026-09-09 : bloquer un
prefixe (ex: "/private/") tout en re-autorisant un sous-chemin precis
a l'interieur (ex: "/private/.assets/") - le plus long prefixe
correspondant gagne (meme ZoneResolver que le reste du projet), donc
une regle "allow" plus specifique lève naturellement le "deny" du
parent. L'activation/desactivation de l'option elle-meme reste le role
de l'ecran Options (menu 2) - ce sous-ecran ne touche que le contenu
de la liste, jamais `enabled`."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.access_rule import (
    AccessRule,
    parse_access_rules,
    validate_access_rule,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _parse_extensions(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


class AccessControlScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("CONTROLE D'ACCES", classes="omega-title")
            yield Static(
                "L'activation de l'option 'access_control' se fait dans le menu Options. "
                "Le plus long prefixe correspondant gagne : une regle 'allow' plus specifique "
                "leve le 'deny' d'un prefixe parent (ex: deny /private/, allow /private/.assets/). "
                "Une regle 'allow' explicite leve aussi deny_hidden_files/deny_patterns sur ce "
                "chemin precis (ecran Securite generique) - un dossier commencant par un point "
                "peut donc etre re-expose deliberement sans desactiver ces regles partout.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="access-rules-table")
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
        table = self.query_one("#access-rules-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Prefixe URL", "Verdict", "Extensions")
        self._refresh_table()

    def _rules(self) -> list[AccessRule]:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return []
        option = result.config.options.get("access_control")
        if option is None:
            return []
        return parse_access_rules(option.settings.get("list", []))

    def _refresh_table(self) -> None:
        table = self.query_one("#access-rules-table", DataTable)
        table.clear()
        for index, rule in enumerate(self._rules()):
            table.add_row(rule.path_prefix, rule.verdict, ", ".join(rule.extensions) or "(toutes)", key=str(index))
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
                    title="AJOUTER UNE REGLE D'ACCES",
                    fields=[
                        ("path_prefix", "Prefixe URL (ex: /private/)", ""),
                        ("verdict", "Verdict (allow/deny)", "deny"),
                        ("extensions", "Extensions concernees (vide=toutes, ex: .key, .pem)", ""),
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
                    title="MODIFIER LA REGLE D'ACCES",
                    fields=[
                        ("path_prefix", "Prefixe URL", rule.path_prefix),
                        ("verdict", "Verdict (allow/deny)", rule.verdict),
                        (
                            "extensions",
                            "Extensions concernees, separees par des virgules (vide = toutes)",
                            ", ".join(rule.extensions),
                        ),
                    ],
                ),
                self._edit_rule,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA REGLE", message="Confirmer la suppression de cette regle d'acces ?"),
                self._delete_rule,
            )

    def _add_rule(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        rule = AccessRule(
            path_prefix=values["path_prefix"].strip(), verdict=values["verdict"].strip().lower(),
            extensions=_parse_extensions(values["extensions"]),
        )
        error = validate_access_rule(rule)
        if error is not None:
            self.query_one("#form-error", Static).update(f"Erreur : {error}")
            return
        rules = self._rules()
        rules.append(rule)
        self._save_rules(rules)

    def _edit_rule(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        rule = AccessRule(
            path_prefix=values["path_prefix"].strip(), verdict=values["verdict"].strip().lower(),
            extensions=_parse_extensions(values["extensions"]),
        )
        error = validate_access_rule(rule)
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

    def _save_rules(self, rules: list[AccessRule]) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("access_control")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["list"] = [
            {"path_prefix": r.path_prefix, "verdict": r.verdict, "extensions": list(r.extensions)} for r in rules
        ]
        new_options = dict(load_result.config.options)
        new_options["access_control"] = Option(name="access_control", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_reload_required(self, self._container, "Regles de controle d'acces mises a jour.")
