"""Sous-ecran WAF - Exclusions et debit (OMEGA-SERV_ETUDE_RATE_LIMIT_
EXCLUSIONS.md, lot 3). Retour utilisateur 2026-10-25 : une page de 129
captures rechargee declenchait le 429 du rate limit natif, puis le ban
omega-jail (`"action": "block"`). Quatre sections :

1. interrupteur + valeurs de la limite globale ;
2. regles par dossier (D1/D2 : remplacent la limite globale, compteur
   propre, 0 = illimite, plus long prefixe gagnant) ;
3. regles par IP/reseau, case "sur" (D3/D4 : un depassement d'une source
   sure est journalise `throttle`, jamais bannissable) + rappel des
   reseaux surs d'office (`reputation.never_auto_block`) ;
4. exclusions d'inspection (prefixes/extensions) - elles sautent le WAF
   natif ET magnet, mais jamais le rate limit (evalue avant).

Chaque enregistrement est valide par `validate_rate_limit_config` (la
partie debit de `config check`) avant d'ecrire quoi que ce soit, puis
rechargement a chaud comme les autres ecrans WAF. Les cles non editees
ici (`algorithm`, `global.key`, `global.response_status`) sont
conservees telles quelles."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.waf.config import (
    PathRateLimitPolicy,
    SourceRateLimitPolicy,
    parse_waf_config,
    validate_rate_limit_config,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._service_reload import reload_service_after_waf_change
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.yes_no import is_yes, to_text

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


def _path_policy_to_dict(policy: PathRateLimitPolicy) -> dict[str, Any]:
    return {"prefix": policy.prefix, "requests": policy.requests, "window_seconds": policy.window_seconds}


def _source_policy_to_dict(policy: SourceRateLimitPolicy) -> dict[str, Any]:
    return {
        "network": policy.network, "requests": policy.requests,
        "window_seconds": policy.window_seconds, "trusted": policy.trusted,
    }


def _split_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


class WafRateLimitScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_path_index: int | None = None
        self._selected_source_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("WAF - EXCLUSIONS ET DÉBIT"), classes="omega-title")
            yield Static(
                _("Une règle par dossier ou par IP/réseau REMPLACE la limite globale (compteur "
                "propre, 0 = illimité). Priorité : dossier, puis IP/réseau, puis limite globale. "
                "Une règle de débit ne désactive jamais l'inspection du WAF."),
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")

            yield Static(_("Limite globale"), classes="omega-subtitle")
            yield Static(_("Rate limit actif (oui/non)"), classes="omega-hint")
            yield Input(id="enabled-input")
            yield Static(_("Requêtes autorisées par fenêtre"), classes="omega-hint")
            yield Input(id="global-requests-input")
            yield Static(_("Fenêtre (secondes)"), classes="omega-hint")
            yield Input(id="global-window-input")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer"), id="save-global", variant="primary")

            yield Static(_("Règles par dossier"), classes="omega-subtitle")
            yield Static(
                _("Un dépassement par une IP publique reste journalisé comme un blocage, donc "
                "bannissable par omega-jail."),
                classes="omega-hint",
            )
            yield DataTable(id="path-policies-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter"), id="add-path", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Modifier"), id="edit-path", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retirer"), id="delete-path", variant="error", disabled=True)

            yield Static(_("Règles par IP / réseau"), classes="omega-subtitle")
            yield Static("", id="trusted-networks-hint", classes="omega-hint")
            yield DataTable(id="source-policies-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter"), id="add-source", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Modifier"), id="edit-source", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retirer"), id="delete-source", variant="error", disabled=True)

            yield Static(_("Exclusions d'inspection"), classes="omega-subtitle")
            yield Static(
                _("Ces chemins ne sont inspectés ni par le WAF natif ni par magnet, mais le rate "
                "limit s'y applique toujours. Valeurs séparées par des virgules."),
                classes="omega-hint",
            )
            yield Static(_("Dossiers non inspectés (ex. /healthz, /static/)"), classes="omega-hint")
            yield Input(id="exclusion-prefixes-input")
            yield Static(_("Extensions non inspectées (ex. .png, .css)"), classes="omega-hint")
            yield Input(id="exclusion-extensions-input")
            yield Static(_("Dossiers dont le corps n'est pas inspecté (ex. /upload/)"), classes="omega-hint")
            yield Input(id="exclusion-body-prefixes-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Enregistrer"), id="save-exclusions", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        path_table = self.query_one("#path-policies-table", DataTable)
        path_table.cursor_type = "row"
        path_table.add_columns(_("Dossier"), _("Requêtes"), _("Fenêtre (s)"))
        source_table = self.query_one("#source-policies-table", DataTable)
        source_table.cursor_type = "row"
        source_table.add_columns(_("Réseau"), _("Requêtes"), _("Fenêtre (s)"), _("Sûr"))
        self._refresh()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    @staticmethod
    def _waf_settings(config: OmegaServConfig) -> dict[str, Any]:
        return dict(config.options["waf"].settings) if "waf" in config.options else {}

    def _refresh(self) -> None:
        config = self._config()
        if config is None:
            self.query_one("#form-error", Static).update(_("Erreur de configuration."))
            return
        waf_config = parse_waf_config(self._waf_settings(config))
        rate_limit = waf_config.rate_limit
        self.query_one("#enabled-input", Input).value = to_text(rate_limit.enabled)
        self.query_one("#global-requests-input", Input).value = str(rate_limit.global_.requests)
        self.query_one("#global-window-input", Input).value = str(rate_limit.global_.window_seconds)

        path_table = self.query_one("#path-policies-table", DataTable)
        path_table.clear()
        self._selected_path_index = None
        self.query_one("#edit-path", Button).disabled = True
        self.query_one("#delete-path", Button).disabled = True
        for index, policy in enumerate(rate_limit.path_policies):
            path_table.add_row(policy.prefix, self._requests_text(policy.requests), str(policy.window_seconds), key=str(index))

        source_table = self.query_one("#source-policies-table", DataTable)
        source_table.clear()
        self._selected_source_index = None
        self.query_one("#edit-source", Button).disabled = True
        self.query_one("#delete-source", Button).disabled = True
        for index, source in enumerate(rate_limit.source_policies):
            source_table.add_row(
                source.network, self._requests_text(source.requests), str(source.window_seconds),
                to_text(source.trusted), key=str(index),
            )

        networks = ", ".join(waf_config.reputation.never_auto_block) or _("aucun")
        self.query_one("#trusted-networks-hint", Static).update(
            _("Toujours sûrs d'office (jamais bannis, réglage never_auto_block) : {networks}. Mettez « Source sûre » à oui "
            "sur une règle pour qu'un dépassement ne soit jamais bannissable. Sans proxy de confiance "
            "actif, une règle couvrant 127.0.0.1/::1 est ignorée (tout le trafic d'un proxy local "
            "arriverait de là).").format(networks=networks)
        )

        exclusions = waf_config.exclusions
        self.query_one("#exclusion-prefixes-input", Input).value = ", ".join(exclusions.path_prefixes)
        self.query_one("#exclusion-extensions-input", Input).value = ", ".join(exclusions.extensions)
        self.query_one("#exclusion-body-prefixes-input", Input).value = ", ".join(exclusions.do_not_inspect_body_path_prefixes)

    @staticmethod
    def _requests_text(requests: int) -> str:
        return _("illimité") if requests == 0 else str(requests)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        index = int(str(event.row_key.value))
        if event.data_table.id == "path-policies-table":
            self._selected_path_index = index
            self.query_one("#edit-path", Button).disabled = False
            self.query_one("#delete-path", Button).disabled = False
            return
        if event.data_table.id == "source-policies-table":
            self._selected_source_index = index
            self.query_one("#edit-source", Button).disabled = False
            self.query_one("#delete-source", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "save-global":
            self._save_global()
            return
        if button_id == "save-exclusions":
            self._save_exclusions()
            return
        if button_id == "add-path":
            self._open_path_form(None)
            return
        if button_id == "edit-path" and self._selected_path_index is not None:
            self._open_path_form(self._selected_path_index)
            return
        if button_id == "delete-path" and self._selected_path_index is not None:
            self.app.push_screen(
                ConfirmScreen(title=_("RETIRER LA RÈGLE"), message=_("Confirmer le retrait de cette règle de débit ?")),
                self._delete_path,
            )
            return
        if button_id == "add-source":
            self._open_source_form(None)
            return
        if button_id == "edit-source" and self._selected_source_index is not None:
            self._open_source_form(self._selected_source_index)
            return
        if button_id == "delete-source" and self._selected_source_index is not None:
            self.app.push_screen(
                ConfirmScreen(title=_("RETIRER LA RÈGLE"), message=_("Confirmer le retrait de cette règle de débit ?")),
                self._delete_source,
            )

    # --- formulaires --------------------------------------------------

    def _open_path_form(self, index: int | None) -> None:
        config = self._config()
        if config is None:
            return
        policies = parse_waf_config(self._waf_settings(config)).rate_limit.path_policies
        current = policies[index] if index is not None and index < len(policies) else PathRateLimitPolicy("/", 600, 60)
        self.app.push_screen(
            DynamicFormScreen(
                title=_("RÈGLE DE DÉBIT PAR DOSSIER"),
                fields=[
                    ("prefix", _("Dossier (ex: /images/)"), current.prefix),
                    ("requests", _("Requêtes autorisées par fenêtre (0 = illimité)"), str(current.requests)),
                    ("window_seconds", _("Fenêtre (secondes)"), str(current.window_seconds)),
                ],
            ),
            lambda values: self._store_path(index, values),
        )

    def _open_source_form(self, index: int | None) -> None:
        config = self._config()
        if config is None:
            return
        policies = parse_waf_config(self._waf_settings(config)).rate_limit.source_policies
        current = (
            policies[index] if index is not None and index < len(policies)
            else SourceRateLimitPolicy("", 600, 60, False)
        )
        self.app.push_screen(
            DynamicFormScreen(
                title=_("RÈGLE DE DÉBIT PAR IP / RÉSEAU"),
                fields=[
                    ("network", _("IP ou réseau (ex: 100.64.0.0/10, 192.168.1.20)"), current.network),
                    ("requests", _("Requêtes autorisées par fenêtre (0 = illimité)"), str(current.requests)),
                    ("window_seconds", _("Fenêtre (secondes)"), str(current.window_seconds)),
                    ("trusted", _("Source sûre - jamais bannie (oui/non)"), to_text(current.trusted)),
                ],
            ),
            lambda values: self._store_source(index, values),
        )

    def _parse_counts(self, values: dict[str, str]) -> tuple[int, int] | None:
        try:
            return int(values["requests"] or "0"), int(values["window_seconds"] or "60")
        except ValueError:
            self.query_one("#form-error", Static).update(_("Valeur invalide : un nombre entier est attendu."))
            return None

    def _store_path(self, index: int | None, values: dict[str, str] | None) -> None:
        if values is None:
            return
        counts = self._parse_counts(values)
        config = self._config()
        if counts is None or config is None:
            return
        policy = PathRateLimitPolicy(prefix=values["prefix"], requests=counts[0], window_seconds=counts[1])
        policies = list(parse_waf_config(self._waf_settings(config)).rate_limit.path_policies)
        if index is None or index >= len(policies):
            policies.append(policy)
        else:
            policies[index] = policy
        self._save_rate_limit_key(config, "path_policies", [_path_policy_to_dict(p) for p in policies])

    def _store_source(self, index: int | None, values: dict[str, str] | None) -> None:
        if values is None:
            return
        counts = self._parse_counts(values)
        config = self._config()
        if counts is None or config is None:
            return
        policy = SourceRateLimitPolicy(
            network=values["network"], requests=counts[0], window_seconds=counts[1], trusted=is_yes(values["trusted"]),
        )
        policies = list(parse_waf_config(self._waf_settings(config)).rate_limit.source_policies)
        if index is None or index >= len(policies):
            policies.append(policy)
        else:
            policies[index] = policy
        self._save_rate_limit_key(config, "source_policies", [_source_policy_to_dict(p) for p in policies])

    def _delete_path(self, confirmed: bool | None) -> None:
        config = self._config()
        if not confirmed or self._selected_path_index is None or config is None:
            return
        policies = list(parse_waf_config(self._waf_settings(config)).rate_limit.path_policies)
        if self._selected_path_index < len(policies):
            del policies[self._selected_path_index]
        self._save_rate_limit_key(config, "path_policies", [_path_policy_to_dict(p) for p in policies])

    def _delete_source(self, confirmed: bool | None) -> None:
        config = self._config()
        if not confirmed or self._selected_source_index is None or config is None:
            return
        policies = list(parse_waf_config(self._waf_settings(config)).rate_limit.source_policies)
        if self._selected_source_index < len(policies):
            del policies[self._selected_source_index]
        self._save_rate_limit_key(config, "source_policies", [_source_policy_to_dict(p) for p in policies])

    # --- enregistrement -----------------------------------------------

    def _save_global(self) -> None:
        config = self._config()
        if config is None:
            self.query_one("#form-error", Static).update(_("Erreur de configuration - impossible d'enregistrer."))
            return
        try:
            requests = int(self.query_one("#global-requests-input", Input).value.strip())
            window_seconds = int(self.query_one("#global-window-input", Input).value.strip())
        except ValueError:
            self.query_one("#form-error", Static).update(_("Valeur invalide : un nombre entier est attendu."))
            return
        settings = self._waf_settings(config)
        rate_limit = dict(settings.get("rate_limit", {}))
        rate_limit["enabled"] = is_yes(self.query_one("#enabled-input", Input).value)
        global_ = dict(rate_limit.get("global", {}))
        global_["requests"] = requests
        global_["window_seconds"] = window_seconds
        rate_limit["global"] = global_
        settings["rate_limit"] = rate_limit
        self._write(config, settings, _("Limite de débit enregistrée."))

    def _save_rate_limit_key(self, config: OmegaServConfig, key: str, value: list[dict[str, Any]]) -> None:
        settings = self._waf_settings(config)
        rate_limit = dict(settings.get("rate_limit", {}))
        rate_limit[key] = value
        settings["rate_limit"] = rate_limit
        self._write(config, settings, _("Règles de débit enregistrées."))

    def _save_exclusions(self) -> None:
        config = self._config()
        if config is None:
            self.query_one("#form-error", Static).update(_("Erreur de configuration - impossible d'enregistrer."))
            return
        settings = self._waf_settings(config)
        exclusions = dict(settings.get("exclusions", {}))
        exclusions["path_prefixes"] = _split_list(self.query_one("#exclusion-prefixes-input", Input).value)
        exclusions["extensions"] = _split_list(self.query_one("#exclusion-extensions-input", Input).value)
        exclusions["do_not_inspect_body_path_prefixes"] = _split_list(
            self.query_one("#exclusion-body-prefixes-input", Input).value
        )
        invalid = [p for p in exclusions["path_prefixes"] + exclusions["do_not_inspect_body_path_prefixes"] if not p.startswith("/")]
        if invalid:
            self.query_one("#form-error", Static).update(
                _("Un dossier doit commencer par « / » : {invalid}").format(invalid=", ".join(invalid))
            )
            return
        settings["exclusions"] = exclusions
        self._write(config, settings, _("Exclusions d'inspection enregistrées."))

    def _write(self, config: OmegaServConfig, settings: dict[str, Any], message: str) -> None:
        error_widget = self.query_one("#form-error", Static)
        errors = validate_rate_limit_config(parse_waf_config(settings).rate_limit)
        if errors:
            error_widget.update("\n".join(errors))
            return
        existing = config.options.get("waf")
        enabled = existing.enabled if existing is not None else False
        new_options = dict(config.options)
        new_options["waf"] = Option(name="waf", enabled=enabled, settings=settings)
        self._container.configuration.save(self._container.config_file, replace(config, options=new_options))
        error_widget.update("")
        self._refresh()
        self.app.notify(message)
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)
