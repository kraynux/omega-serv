# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran WAF - Custom (retour utilisateur 2026-09-13 : "j'ai cree
une regle dans l'interface, elle ne se declenche jamais, les logs sont
vides" - le pack `secure/waf/rules/custom.json` existait deja comme
gabarit vide, mais rien ne permettait d'y ecrire une VRAIE regle depuis
l'interface, et meme en ajoutant son chemin via "Modules", l'utilisateur
avait cree la confusion inverse : ajouter le PACK (le conteneur) n'est
pas creer une REGLE (le contenu)). Cet ecran fait les deux a la fois :
ecrit la regle dans custom.json ET s'assure que ce chemin est bien
reference dans rule_paths (jamais une etape manuelle separee a retenir),
en reutilisant les MEMES fonctions pures de validation que le chargeur
reel (domain/security/waf/rule_validation.py) - une regle refusee ici
serait de toute facon refusee au chargement, jamais une double logique
de validation a maintenir."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.security.waf.rule_validation import parse_rule_pack, validate_rule_pack
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._service_reload import reload_service_after_waf_change
from omega_serv.interfaces.tui.screens._waf_rule_paths import (
    get_waf_rule_paths,
    with_waf_rule_paths,
)
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.waf_custom_rule_wizard_screen import (
    WafCustomRuleWizardScreen,
)

if TYPE_CHECKING:
    from pathlib import Path

    from omega_serv.bootstrap.container import DependencyContainer

_CUSTOM_PACK_RELATIVE_PATH = "secure/waf/rules/custom.json"
_DEFAULT_PACK: dict[str, Any] = {"version": 1, "pack": "custom", "enabled": True, "rules": []}


class WafCustomRuleScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("WAF - REGLES CUSTOM", classes="omega-title")
            yield Static(
                f"Ecrit dans {_CUSTOM_PACK_RELATIVE_PATH} et l'ajoute automatiquement aux packs "
                "references (rule_paths) - jamais une etape separee a retenir.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="custom-rules-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter une regle", id="add-rule", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete-rule", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#custom-rules-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Description", "Scope", "Motif", "Poids", "Actif")
        self._refresh()

    def _pack_path(self) -> Path:
        return self._container.project_root / _CUSTOM_PACK_RELATIVE_PATH

    def _load_pack(self) -> dict[str, Any]:
        path = self._pack_path()
        if not self._container.filesystem.exists(path):
            return dict(_DEFAULT_PACK)
        try:
            return cast("dict[str, Any]", json.loads(self._container.filesystem.read_text(path)))
        except (OSError, ValueError):
            return dict(_DEFAULT_PACK)

    def _refresh(self) -> None:
        table = self.query_one("#custom-rules-table", DataTable)
        table.clear()
        self._selected_index = None
        self.query_one("#delete-rule", Button).disabled = True
        pack = self._load_pack()
        for index, rule in enumerate(pack.get("rules", [])):
            table.add_row(
                rule.get("id", "?"), rule.get("description", ""), ", ".join(rule.get("scope", [])),
                rule.get("pattern", ""), str(rule.get("weight", 1)),
                "oui" if rule.get("enabled", True) else "non",
                key=str(index),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#delete-rule", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "add-rule":
            self.app.push_screen(WafCustomRuleWizardScreen(), self._add_rule)
            return
        if event.button.id == "delete-rule" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA REGLE", message="Confirmer la suppression de cette regle custom ?"),
                self._delete_rule,
            )

    def _next_rule_id(self, pack: dict[str, Any]) -> str:
        # Genere automatiquement (retour utilisateur 2026-09-14 :
        # l'assistant ne demande plus d'identifiant, un champ technique
        # de moins pour un utilisateur qui ne sait pas coder) - jamais
        # de collision avec un id existant, y compris un id non
        # standard laisse par une edition manuelle du JSON.
        existing_ids = {rule.get("id", "") for rule in pack.get("rules", [])}
        index = 1
        while f"CUSTOM-{index:03d}" in existing_ids:
            index += 1
        return f"CUSTOM-{index:03d}"

    def _add_rule(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        error_widget = self.query_one("#form-error", Static)
        try:
            weight = int(values["weight"].strip())
        except ValueError:
            error_widget.update(f"Poids invalide (entier attendu) : {values['weight']!r}")
            return
        scope = [s.strip() for s in values["scope"].split(",") if s.strip()]
        pack = self._load_pack()
        rule = {
            "id": self._next_rule_id(pack),
            "description": values["description"].strip(),
            "scope": scope,
            "pattern": values["pattern"],
            "weight": weight,
            "case_insensitive": values["case_insensitive"].strip().lower() in ("oui", "true", "1", "o", "y"),
            "enabled": values["enabled"].strip().lower() in ("oui", "true", "1", "o", "y"),
        }
        pack["rules"] = [*pack.get("rules", []), rule]

        # Reutilise les MEMES fonctions de validation que le chargeur
        # reel (infrastructure/waf/rule_pack_loader.py) - une regle
        # refusee ici le serait de toute facon au chargement, jamais une
        # seconde logique de validation a maintenir en parallele.
        try:
            parsed = parse_rule_pack(pack)
        except (KeyError, TypeError) as exc:
            error_widget.update(f"Regle invalide : {exc}")
            return
        errors = validate_rule_pack(parsed)
        if errors:
            error_widget.update("Erreur :\n" + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.filesystem.make_directory(self._pack_path().parent)
        self._container.filesystem.write_text(self._pack_path(), json.dumps(pack, indent=2, ensure_ascii=False))
        self._ensure_pack_referenced()
        error_widget.update("")
        self._refresh()
        self.app.notify(f"Regle {rule['id']!r} ajoutee et pack custom reference dans rule_paths.")
        reload_message = reload_service_after_waf_change(self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _delete_rule(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        pack = self._load_pack()
        rules = list(pack.get("rules", []))
        del rules[self._selected_index]
        pack["rules"] = rules
        self._container.filesystem.write_text(self._pack_path(), json.dumps(pack, indent=2, ensure_ascii=False))
        self._refresh()
        self.app.notify("Regle custom supprimee.")
        reload_message = reload_service_after_waf_change(self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _ensure_pack_referenced(self) -> None:
        # Retour utilisateur 2026-09-13 (cause directe de la confusion
        # initiale) : creer une regle ici doit suffire, jamais exiger un
        # aller-retour manuel par "Modules" pour reference le pack.
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return
        paths = get_waf_rule_paths(load_result.config)
        if _CUSTOM_PACK_RELATIVE_PATH in paths:
            return
        paths.append(_CUSTOM_PACK_RELATIVE_PATH)
        new_config = with_waf_rule_paths(load_result.config, paths)
        self._container.configuration.save(self._container.config_file, new_config)
