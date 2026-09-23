"""Sous-ecran WAF - Modules (retour utilisateur 2026-09-13,
restructuration Etat/Modules/Tester/Custom - renomme depuis l'ancien
WafMenuScreen unique, "Tester" et "Custom" en sont extraits en ecrans
separes). Trois sections : basculer les 2 reglages operationnels les
plus courants (mode/on_internal_error), gerer les packs de regles
(rule_paths - retour utilisateur 2026-09-13 : "le WAF ne marche pas" -
vrai trou trouve, le WAF tournait avec ZERO regle chargee car rien ne
permettait de configurer ceci autrement qu'a la main dans le JSON) et
gerer la blocklist (container.blocklist_port_factory, injecte depuis
__main__.py car le cas d'usage touche infrastructure/ transitivement).
Les champs restants de WafConfig -inspect/scoring/rate_limit/
reputation/exclusions/logging- restent avances, edition manuelle pour
l'instant, aucun besoin confirme de formulaire dedie - D-008."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.security.manage_blocklist import (
    ManageBlocklistResult,
    add_blocklist_entry,
    remove_blocklist_entry,
)
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._service_reload import reload_service_after_waf_change
from omega_serv.interfaces.tui.screens._waf_rule_paths import (
    get_waf_rule_paths,
    with_waf_rule_paths,
)
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.waf_rule_pack_picker_screen import WafRulePackPickerScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


class WafModulesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_network: str | None = None
        self._selected_rule_path_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("WAF - MODULES", classes="omega-title")
            yield Static(
                "L'activation de l'option 'waf' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")

            yield Static("Mode (log-only/block)", classes="omega-subtitle")
            yield Input(id="mode-input")
            yield Static("Comportement en cas d'erreur interne (fail-open/fail-closed)", classes="omega-subtitle")
            yield Input(id="on-internal-error-input")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Enregistrer", id="save-mode", variant="primary")

            yield Static("Packs de regles (rule_paths)", classes="omega-subtitle")
            yield Static(self._available_packs_hint(), id="available-packs-hint", classes="omega-hint")
            yield DataTable(id="rule-paths-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter un pack", id="add-rule-path", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retirer", id="delete-rule-path", variant="error", disabled=True)

            yield Static("Liste de blocage", classes="omega-subtitle")
            yield DataTable(id="blocklist-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add-entry", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete-entry", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#blocklist-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Reseau", "Motif", "Expiration", "Source")
        rule_paths_table = self.query_one("#rule-paths-table", DataTable)
        rule_paths_table.cursor_type = "row"
        rule_paths_table.add_columns("Chemin du pack")
        self._refresh()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _available_packs_hint(self) -> str:
        rules_dir = self._container.project_root / "secure" / "waf" / "rules"
        if not rules_dir.is_dir():
            return "Aucun pack trouve sous secure/waf/rules/."
        packs = sorted(p.name for p in rules_dir.glob("*.json"))
        if not packs:
            return "Aucun pack trouve sous secure/waf/rules/."
        listed = ", ".join(f"secure/waf/rules/{name}" for name in packs)
        return f"Packs disponibles sur disque : {listed}"

    def _refresh(self) -> None:
        config = self._config()
        if config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration.")
            return
        settings = config.options["waf"].settings if "waf" in config.options else {}
        waf_config = parse_waf_config(settings)
        self.query_one("#mode-input", Input).value = waf_config.mode
        self.query_one("#on-internal-error-input", Input).value = waf_config.on_internal_error

        rule_paths_table = self.query_one("#rule-paths-table", DataTable)
        rule_paths_table.clear()
        self._selected_rule_path_index = None
        self.query_one("#delete-rule-path", Button).disabled = True
        for index, rule_path in enumerate(get_waf_rule_paths(config)):
            rule_paths_table.add_row(rule_path, key=str(index))

        table = self.query_one("#blocklist-table", DataTable)
        table.clear()
        self._selected_network = None
        self.query_one("#delete-entry", Button).disabled = True
        factory = self._container.blocklist_port_factory
        if factory is None:
            return
        port = factory(config, self._container.filesystem, self._container.project_root, self._container.clock)
        for entry in port.list_entries():
            table.add_row(entry.network, entry.reason, entry.expires_at or "permanent", entry.source, key=entry.network)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "rule-paths-table":
            self._selected_rule_path_index = int(str(event.row_key.value))
            self.query_one("#delete-rule-path", Button).disabled = False
            return
        self._selected_network = str(event.row_key.value)
        self.query_one("#delete-entry", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "save-mode":
            self._save_mode()
            return
        if button_id == "add-rule-path":
            config = self._config()
            existing_paths = get_waf_rule_paths(config) if config is not None else []
            self.app.push_screen(
                WafRulePackPickerScreen(
                    filesystem=self._container.filesystem,
                    project_root=self._container.project_root,
                    existing_paths=existing_paths,
                ),
                self._add_rule_path,
            )
            return
        if button_id == "delete-rule-path" and self._selected_rule_path_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="RETIRER LE PACK", message="Confirmer le retrait de ce pack de regles ?"),
                self._delete_rule_path,
            )
            return
        if button_id == "add-entry":
            self.app.push_screen(
                DynamicFormScreen(
                    title="AJOUTER UNE ENTREE",
                    fields=[
                        ("network", "Reseau (ex: 203.0.113.25/32)", ""),
                        ("reason", "Motif", ""),
                        ("duration_seconds", "Duree en secondes (vide = permanent)", ""),
                        ("confirm_permanent", "Confirmer un bannissement permanent (oui/non)", "non"),
                    ],
                ),
                self._add_entry,
            )
            return
        if button_id == "delete-entry" and self._selected_network is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER L'ENTREE", message=f"Confirmer la suppression de {self._selected_network!r} ?"),
                self._delete_entry,
            )

    def _add_rule_path(self, path: str | None) -> None:
        if path is None:
            return
        config = self._config()
        if config is None:
            return
        paths = get_waf_rule_paths(config)
        paths.append(path)
        self._save_rule_paths(paths)

    def _delete_rule_path(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_rule_path_index is None:
            return
        config = self._config()
        if config is None:
            return
        paths = get_waf_rule_paths(config)
        del paths[self._selected_rule_path_index]
        self._save_rule_paths(paths)

    def _save_rule_paths(self, paths: list[str]) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        new_config = with_waf_rule_paths(load_result.config, paths)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh()
        self.app.notify("Packs de regles WAF mis a jour.")
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _save_mode(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration - impossible d'enregistrer.")
            return
        mode = self.query_one("#mode-input", Input).value.strip()
        on_internal_error = self.query_one("#on-internal-error-input", Input).value.strip()
        if mode not in ("log-only", "block"):
            error_widget.update(f"Mode invalide : {mode!r} (attendu : log-only, block)")
            return
        if on_internal_error not in ("fail-open", "fail-closed"):
            error_widget.update(f"Valeur invalide : {on_internal_error!r} (attendu : fail-open, fail-closed)")
            return

        existing = load_result.config.options.get("waf")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["mode"] = mode
        new_settings["on_internal_error"] = on_internal_error
        new_options = dict(load_result.config.options)
        new_options["waf"] = Option(name="waf", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        self.app.notify("Reglages WAF enregistres.")
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    def _add_entry(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        config = self._config()
        factory = self._container.blocklist_port_factory
        if config is None or factory is None:
            return
        duration_text = values["duration_seconds"].strip()
        duration_seconds = None
        if duration_text:
            try:
                duration_seconds = int(duration_text)
            except ValueError:
                self.query_one("#form-error", Static).update(f"Duree invalide (nombre attendu) : {duration_text!r}")
                return
        confirm_permanent = values["confirm_permanent"].strip().lower() in ("oui", "true", "1", "o", "y")
        port = factory(config, self._container.filesystem, self._container.project_root, self._container.clock)
        result = add_blocklist_entry(port, values["network"], values["reason"], duration_seconds, confirm_permanent)
        self._report(result)

    def _delete_entry(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_network is None:
            return
        config = self._config()
        factory = self._container.blocklist_port_factory
        if config is None or factory is None:
            return
        port = factory(config, self._container.filesystem, self._container.project_root, self._container.clock)
        result = remove_blocklist_entry(port, self._selected_network)
        self._report(result)

    def _report(self, result: ManageBlocklistResult) -> None:
        error_widget = self.query_one("#form-error", Static)
        error_widget.update("" if result.success else f"Erreur : {result.message}")
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._refresh()
