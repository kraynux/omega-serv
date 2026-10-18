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
from omega_serv.application.security.editable_list_file import inspect_list_file
from omega_serv.application.security.load_keyword_list import (
    ListLoadRequest,
    load_keyword_list_into_config,
    remove_keyword_list_entry,
    update_keyword_list_entry,
)
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_account,
)
from omega_serv.domain.security.waf.keyword_list import tokens_from_text
from omega_serv.domain.security.waf.rule_validation import parse_rule_pack, validate_rule_pack
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._service_reload import reload_service_after_waf_change
from omega_serv.interfaces.tui.screens._waf_list_choices import gravity_label
from omega_serv.interfaces.tui.screens._waf_rule_paths import (
    get_waf_rule_paths,
    with_waf_rule_paths,
)
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.path_list_editor_screen import PathListEditorScreen
from omega_serv.interfaces.tui.screens.waf_custom_rule_wizard_screen import (
    WafCustomRuleWizardScreen,
)
from omega_serv.interfaces.tui.screens.waf_keyword_list_settings_screen import (
    KeywordListSettingsScreen,
)

if TYPE_CHECKING:
    from pathlib import Path

    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_CUSTOM_PACK_RELATIVE_PATH = "secure/waf/rules/custom.json"
_DEFAULT_PACK: dict[str, Any] = {"version": 1, "pack": "custom", "enabled": True, "rules": []}


class WafCustomRuleScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None
        # Ligne selectionnee : ("rule", index dans custom.json) ou ("list", id de la keyword_list)
        # (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md lot 7 : regles ET listes dans un seul tableau).
        self._selected: tuple[str, str] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("WAF - REGLES ET LISTES CUSTOM", classes="omega-title")
            yield Static(
                f"Regles : ecrites dans {_CUSTOM_PACK_RELATIVE_PATH}, ajoutees automatiquement aux packs "
                "references (rule_paths). Listes : fichiers de secure/waf/rules/keywords/, chargees "
                "explicitement par l'assistant (Ajouter -> CHARGER une liste). Colonne Type = la difference.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="custom-rules-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add-rule", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Modifier", id="list-settings", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Editer la liste", id="edit-list", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Activer/Desactiver", id="toggle-enabled", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete-rule", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#custom-rules-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Type", "ID", "Nom / description", "Portee", "Detail", "Gravite", "Actif")
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
        self._selected = None
        self._update_buttons()
        pack = self._load_pack()
        for index, rule in enumerate(pack.get("rules", [])):
            table.add_row(
                "Regle", rule.get("id", "?"), rule.get("description", ""), ", ".join(rule.get("scope", [])),
                rule.get("pattern", ""), str(rule.get("weight", 1)),
                "oui" if rule.get("enabled", True) else "non",
                key=f"rule:{index}",
            )
        for entry in self._list_entries():
            table.add_row(
                "Liste", str(entry.get("id")), str(entry.get("label") or entry.get("id")),
                self._list_scope_text(entry), self._list_detail(entry), self._list_gravity_text(entry),
                "oui" if entry.get("enabled", True) else "non",
                key=f"list:{entry.get('id')}",
            )

    # ---- listes (keyword_lists) -----------------------------------------------
    def _list_entries(self) -> list[dict[str, Any]]:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None or "waf" not in load_result.config.options:
            return []
        settings = load_result.config.options["waf"].settings
        return [dict(item) for item in settings.get("rules", {}).get("keyword_lists", [])]

    def _list_entry(self, list_id: str) -> dict[str, Any] | None:
        return next((e for e in self._list_entries() if str(e.get("id")) == list_id), None)

    @staticmethod
    def _list_scope_text(entry: dict[str, Any]) -> str:
        if entry.get("match") == "path":
            return "chemins (debut)" if entry.get("anchor") == "root" else "chemins (partout)"
        return ", ".join(entry.get("scope", []))

    def _list_detail(self, entry: dict[str, Any]) -> str:
        """Nombre d'entrees, ou un avertissement visible plutot qu'un ecran en
        erreur si le fichier est absent/illisible (plan lot 7.2)."""
        relative = str(entry.get("file", ""))
        status = inspect_list_file(
            self._container.file_access, self._container.project_root, relative, self._service_account(),
        )
        if status.location_error is not None:
            return "⚠ emplacement refuse"
        if not status.exists:
            return "⚠ fichier absent"
        if status.service_check == "unreadable":
            return "⚠ illisible par le service"
        try:
            text = self._container.filesystem.read_text(self._container.project_root / relative)
        except OSError:
            return "⚠ fichier illisible"
        return f"{len(tokens_from_text(text))} entrees"

    @staticmethod
    def _list_gravity_text(entry: dict[str, Any]) -> str:
        observe = bool(entry.get("observe_only"))
        label = gravity_label(int(entry.get("weight", 1)), observe)
        threshold = int(entry.get("escalation_threshold", 0))
        if observe or threshold <= 0:
            return label
        window = int(entry.get("escalation_window_seconds", 600)) // 60
        duration = entry.get("auto_block_duration_seconds")
        ban = f" -> ban {int(duration) // 3600} h" if duration else ""
        return f"{label}, {threshold} en {window} min{ban}"

    def _service_account(self) -> str | None:
        return resolve_current_service_account(
            self._container.instance_registry, self._container.filesystem, self._container.settings_store,
            self._container.project_root, self._container.systemd_unit_dir,
        )

    def _update_buttons(self) -> None:
        kind = self._selected[0] if self._selected else None
        self.query_one("#delete-rule", Button).disabled = kind is None
        self.query_one("#delete-rule", Button).label = "Retirer" if kind == "list" else "Supprimer"
        self.query_one("#toggle-enabled", Button).disabled = kind is None
        self.query_one("#edit-list", Button).disabled = kind != "list"
        self.query_one("#list-settings", Button).disabled = kind != "list"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        kind, _, key = str(event.row_key.value).partition(":")
        self._selected = (kind, key)
        self._selected_index = int(key) if kind == "rule" else None
        self._update_buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "add-rule":
            self.app.push_screen(WafCustomRuleWizardScreen(self._container), self._add_rule)
            return
        if event.button.id == "delete-rule" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA REGLE", message="Confirmer la suppression de cette regle custom ?"),
                self._delete_rule,
            )
            return
        if self._selected is None:
            return
        kind, key = self._selected
        if event.button.id == "toggle-enabled":
            if kind == "rule":
                self._toggle_rule(int(key))
            else:
                self._update_list(key, None)
        elif kind != "list":
            return
        elif event.button.id == "delete-rule":
            self.app.push_screen(
                ConfirmScreen(
                    title="RETIRER LA LISTE",
                    message=f"La liste {key!r} ne sera plus chargee par le WAF. Son fichier est CONSERVE "
                    "(toujours disponible dans l'assistant).",
                ),
                lambda confirmed: self._remove_list(key) if confirmed else None,
            )
        elif event.button.id == "edit-list":
            self._open_list_editor(key)
        elif event.button.id == "list-settings":
            entry = self._list_entry(key)
            if entry is not None:
                self.app.push_screen(KeywordListSettingsScreen(entry), lambda changes: self._update_list(key, changes))

    def _save_config_and_reload(self, config: OmegaServConfig, message: str, extra: tuple[str, ...] = ()) -> None:
        self._container.configuration.save(self._container.config_file, config)
        self.query_one("#form-error", Static).update("")
        self._refresh()
        self.app.notify(message)
        for line in extra:
            self.app.notify(line, timeout=10)
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _update_list(self, list_id: str, changes: dict[str, Any] | None) -> None:
        """`changes=None` = bascule Activer/Desactiver."""
        load_result = load_config(self._container.configuration, self._container.config_file)
        entry = self._list_entry(list_id)
        if not load_result.success or load_result.config is None or entry is None:
            return
        if changes is None:
            changes = {"enabled": not entry.get("enabled", True)}
        result = update_keyword_list_entry(
            load_result.config, list_id, changes, filesystem=self._container.filesystem,
            project_root=self._container.project_root, config_check=self._container.config_check_runner,
        )
        if not result.loaded or result.config is None:
            self.query_one("#form-error", Static).update(f"Modification refusee : {result.error}")
            return
        self._save_config_and_reload(result.config, f"Liste {list_id!r} mise a jour.", result.messages)

    def _remove_list(self, list_id: str) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return
        self._save_config_and_reload(
            remove_keyword_list_entry(load_result.config, list_id),
            f"Liste {list_id!r} retiree du WAF (fichier conserve).",
        )

    def _open_list_editor(self, list_id: str) -> None:
        entry = self._list_entry(list_id)
        if entry is None:
            return
        relative = str(entry.get("file", ""))
        name = relative.rsplit("/", 1)[-1]
        self.app.push_screen(
            PathListEditorScreen(
                container=self._container, relative_path=relative,
                anchor=str(entry.get("anchor", "any_segment")),
                title=f"EDITION - {entry.get('label') or list_id}",
                reference_name=name if name in self._container.keyword_references.names() else None,
                match=str(entry.get("match", "substring")),
            ),
            lambda _result: self._refresh(),
        )

    def _toggle_rule(self, index: int) -> None:
        pack = self._load_pack()
        rules = list(pack.get("rules", []))
        if not 0 <= index < len(rules):
            return
        rules[index] = {**rules[index], "enabled": not rules[index].get("enabled", True)}
        pack["rules"] = rules
        self._container.filesystem.write_text(self._pack_path(), json.dumps(pack, indent=2, ensure_ascii=False))
        self._refresh()
        self.app.notify(f"Regle {rules[index].get('id')!r} {'activee' if rules[index]['enabled'] else 'desactivee'}.")
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _next_rule_id(self, pack: dict[str, Any]) -> str:
        existing_ids = {rule.get("id", "") for rule in pack.get("rules", [])}
        index = 1
        while f"CUSTOM-{index:03d}" in existing_ids:
            index += 1
        return f"CUSTOM-{index:03d}"

    def _add_rule(self, values: dict[str, Any] | None) -> None:
        if values is None:
            return
        if values.get("kind") == "keyword_list":
            self._load_list(values["request"])
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
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _load_list(self, request: ListLoadRequest) -> None:
        """Chargement EXPLICITE d'une liste (OMEGA-SERV_PLAN-DETAILLE_
        SENSITIVE_PATHS.md lot 6.3) : toutes les verifications sont dans le cas
        d'usage ; la configuration n'est ecrite que si elles passent toutes."""
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Configuration illisible : liste non chargee.")
            return
        result = load_keyword_list_into_config(
            load_result.config, request,
            file_access=self._container.file_access, filesystem=self._container.filesystem,
            references=self._container.keyword_references, project_root=self._container.project_root,
            service_account=resolve_current_service_account(
                self._container.instance_registry, self._container.filesystem, self._container.settings_store,
                self._container.project_root, self._container.systemd_unit_dir,
            ),
            config_check=self._container.config_check_runner,
        )
        if not result.loaded or result.config is None:
            error_widget.update(f"Liste non chargee : {result.error}")
            return
        self._container.configuration.save(self._container.config_file, result.config)
        error_widget.update("")
        self._refresh()
        self.app.notify(f"Liste {result.list_id!r} chargee dans le WAF.")
        for message in result.messages:
            self.app.notify(message, timeout=10)
        reload_message = reload_service_after_waf_change(self, self._container)
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
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _ensure_pack_referenced(self) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return
        paths = get_waf_rule_paths(load_result.config)
        if _CUSTOM_PACK_RELATIVE_PATH in paths:
            return
        paths.append(_CUSTOM_PACK_RELATIVE_PATH)
        new_config = with_waf_rule_paths(load_result.config, paths)
        self._container.configuration.save(self._container.config_file, new_config)
