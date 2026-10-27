"""Sous-ecran Securite generique (plan interface §7) - SecurityConfig
(methodes autorisees, CSP, en-tetes, HSTS). Champs booleens en "oui/non"
texte (meme convention simple que le reste de ce menu, pas de nouveau
type de widget pour un seul sous-ecran).

Zones CSP (spec §12.4, retour utilisateur 2026-10-10 : "autoriser des
regles conditionnelles pour des dossiers choisis") : CRUD immediat
(ajout/retrait appliques des le clic, comme les packs de regles WAF
dans WafModulesScreen - jamais groupes avec le bouton "Enregistrer" des
champs scalaires ci-dessus)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.validation import validate_config
from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.domain.security.csp import DEFAULT_CSP_POLICY
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.csp_zone_wizard_screen import CspZoneWizardScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required
from omega_serv.interfaces.tui.yes_no import is_yes, to_text

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_POLICY_PREVIEW_MAX_CHARS = 60


def _bool_to_text(value: bool) -> str:
    return to_text(value)


def _text_to_bool(value: str) -> bool:
    return is_yes(value)


class SecurityScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_zone_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static(_("SÉCURITÉ GÉNÉRIQUE"), classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static(_("Méthodes autorisées (séparées par des virgules)"), classes="omega-subtitle")
            yield Input(id="allowed-methods-input")
            yield Static(_("Refuser les fichiers cachés (oui/non)"), classes="omega-subtitle")
            yield Input(id="deny-hidden-files-input")
            yield Static(_("Mode CSP (enforce/report-only)"), classes="omega-subtitle")
            yield Input(id="csp-mode-input")
            yield Static(_("Cross-Origin-Embedder-Policy (unsafe-none/require-corp/credentialless)"), classes="omega-subtitle")
            yield Input(id="coep-mode-input")
            yield Static(_("En-têtes de sécurité actifs (oui/non)"), classes="omega-subtitle")
            yield Input(id="security-headers-input")
            yield Static(_("HSTS actif (oui/non)"), classes="omega-subtitle")
            yield Input(id="hsts-enabled-input")
            yield Static(_("HSTS max-age en secondes"), classes="omega-subtitle")
            yield Input(id="hsts-max-age-input")
            yield Static(_("HSTS includeSubDomains (oui/non)"), classes="omega-subtitle")
            yield Input(id="hsts-subdomains-input")
            yield Static(_("HSTS preload (oui/non)"), classes="omega-subtitle")
            yield Input(id="hsts-preload-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Enregistrer"), id="save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")

            yield Static(_("Zones CSP (exceptions par chemin - jamais le défaut global)"), classes="omega-subtitle")
            yield Static(
                _("Une zone remplace ENTIÈREMENT la CSP par défaut pour son préfixe (jamais une "
                "fusion) - une exception comme 'unsafe-inline' y reste signalée par "
                "'omega-serv audit security', jamais silencieuse."),
                classes="omega-hint",
            )
            yield DataTable(id="csp-zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter une zone"), id="add-zone", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retirer"), id="delete-zone", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#csp-zones-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Préfixe"), _("Politique"))
        self._refresh()

    def _refresh(self) -> None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success:
            self.query_one("#form-error", Static).update(
                _("Erreur de configuration : ") + "; ".join(result.errors)
            )
            self.query_one("#save", Button).disabled = True
            return
        assert result.config is not None
        security = result.config.security
        self.query_one("#allowed-methods-input", Input).value = ", ".join(security.allowed_methods)
        self.query_one("#deny-hidden-files-input", Input).value = _bool_to_text(security.deny_hidden_files)
        self.query_one("#csp-mode-input", Input).value = security.csp_mode
        self.query_one("#coep-mode-input", Input).value = security.coep_mode
        self.query_one("#security-headers-input", Input).value = _bool_to_text(security.security_headers_enabled)
        self.query_one("#hsts-enabled-input", Input).value = _bool_to_text(security.hsts_enabled)
        self.query_one("#hsts-max-age-input", Input).value = str(security.hsts_max_age)
        self.query_one("#hsts-subdomains-input", Input).value = _bool_to_text(security.hsts_include_subdomains)
        self.query_one("#hsts-preload-input", Input).value = _bool_to_text(security.hsts_preload)

        table = self.query_one("#csp-zones-table", DataTable)
        table.clear()
        self._selected_zone_index = None
        self.query_one("#delete-zone", Button).disabled = True
        for index, zone in enumerate(security.csp_zones):
            preview = zone.data if len(zone.data) <= _POLICY_PREVIEW_MAX_CHARS else zone.data[:_POLICY_PREVIEW_MAX_CHARS] + "..."
            table.add_row(zone.path_prefix, preview, key=str(index))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_zone_index = int(str(event.row_key.value))
        self.query_one("#delete-zone", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._save()
            return
        if event.button.id == "add-zone":
            self.app.push_screen(
                CspZoneWizardScreen(current_policy=DEFAULT_CSP_POLICY),
                self._add_zone,
            )
            return
        if event.button.id == "delete-zone" and self._selected_zone_index is not None:
            self.app.push_screen(
                ConfirmScreen(title=_("RETIRER LA ZONE"), message=_("Confirmer le retrait de cette zone CSP ?")),
                self._delete_zone,
            )

    def _save(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            error_widget.update(_("Erreur de configuration : ") + "; ".join(load_result.errors))
            return
        assert load_result.config is not None

        max_age_text = self.query_one("#hsts-max-age-input", Input).value.strip()
        try:
            hsts_max_age = int(max_age_text)
        except ValueError:
            error_widget.update(_("HSTS max-age invalide (nombre attendu) : {max_age_text!r}").format(max_age_text=max_age_text))
            return

        allowed_methods = tuple(
            item.strip().upper() for item in self.query_one("#allowed-methods-input", Input).value.split(",") if item.strip()
        )
        new_security = replace(
            load_result.config.security,
            allowed_methods=allowed_methods,
            deny_hidden_files=_text_to_bool(self.query_one("#deny-hidden-files-input", Input).value),
            csp_mode=self.query_one("#csp-mode-input", Input).value.strip(),
            coep_mode=self.query_one("#coep-mode-input", Input).value.strip(),
            security_headers_enabled=_text_to_bool(self.query_one("#security-headers-input", Input).value),
            hsts_enabled=_text_to_bool(self.query_one("#hsts-enabled-input", Input).value),
            hsts_max_age=hsts_max_age,
            hsts_include_subdomains=_text_to_bool(self.query_one("#hsts-subdomains-input", Input).value),
            hsts_preload=_text_to_bool(self.query_one("#hsts-preload-input", Input).value),
        )
        new_config = replace(load_result.config, security=new_security)

        errors = validate_config(new_config)
        if errors:
            error_widget.update(_("Erreur de validation :\n") + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        notify_reload_required(self, self._container, _("Sécurité générique enregistrée."))

    def _add_zone(self, result: tuple[str, str] | None) -> None:
        if result is None:
            return
        path_prefix, policy = result
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update(_("Erreur de configuration - impossible d'enregistrer."))
            return

        new_zone = Zone(path_prefix, policy)
        new_security = replace(load_result.config.security, csp_zones=(*load_result.config.security.csp_zones, new_zone))
        new_config = replace(load_result.config, security=new_security)

        errors = validate_config(new_config)
        if errors:
            error_widget.update(_("Erreur de validation :\n") + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        self._refresh()
        notify_reload_required(self, self._container, _("Zone CSP ajoutée."))

    def _delete_zone(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_zone_index is None:
            return
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update(_("Erreur de configuration - impossible d'enregistrer."))
            return

        zones = list(load_result.config.security.csp_zones)
        del zones[self._selected_zone_index]
        new_security = replace(load_result.config.security, csp_zones=tuple(zones))
        new_config = replace(load_result.config, security=new_security)

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        self._refresh()
        notify_reload_required(self, self._container, _("Zone CSP retirée."))
