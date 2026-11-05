"""RIPOSTE - Reglages (topo §6.4-6 ; lot 5) : paliers de duree, fenetre de recidive, silence entre deux
episodes, conservation de l'historique, plafond de bans simultanes, exemptions de la configuration ; les
exclusions heritees du WAF en lecture seule ; les exemptions ajoutees par « Lever et exempter » (base),
retirables. Le module lui-meme s'active dans Options (redemarrage complet), jamais par un profil.

Enregistrer valide d'abord (aucune ecriture si un reglage est refuse), puis le processus relit."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.riposte.console import (
    GlobalSettings,
    riposte_config_of,
    riposte_enabled,
    save_global_settings,
)
from omega_serv.application.riposte.safety import riposte_exempt_networks
from omega_serv.core.i18n import _
from omega_serv.domain.security.riposte.config import DEFAULT_TIERS_SECONDS
from omega_serv.domain.security.riposte.durations import (
    duration_text,
    durations_text,
    parse_duration,
    parse_durations,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._riposte_access import (
    RiposteAccessMixin,
    StoreUnavailable,
    cell,
    local_time,
    show,
)
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_NETWORKS_EXAMPLE = ("192.0.2.0/24", "2001:db8::/32")
_DURATION_FIELDS = (
    ("recidive-window", _("Fenêtre de récidive"),
     _("Un retour dans cette fenêtre fait monter le palier ; une fenêtre entière sans retour ramène au palier 1.")),
    ("episode-gap", _("Silence entre deux épisodes"),
     _("Au-delà de ce silence, la source qui revient compte comme un « retour » (nouvel épisode).")),
    ("retention", _("Conservation de l'historique"),
     _("Les épisodes et les actions terminées plus anciens sont effacés (données personnelles).")),
)


class RiposteSettingsScreen(RiposteAccessMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_exemption: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RIPOSTE - RÉGLAGES"), classes="omega-title")
            yield Static("", id="settings-module", classes="omega-hint")
            yield Static("", id="settings-error", classes="omega-hint")
            yield Static(_("Paliers de durée des bans"), classes="omega-subtitle")
            yield Static(_("Du premier ban au plus long, séparés par des virgules (s, m, h, d). Au-delà de 7 jours : "
                           "refusé ici (une politique peut le demander, avec confirmation)."), classes="omega-hint")
            yield Input(placeholder=durations_text(DEFAULT_TIERS_SECONDS), id="tiers-input")
            for field_id, label, hint in _DURATION_FIELDS:
                yield Static(label, classes="omega-subtitle")
                yield Static(hint, classes="omega-hint")
                yield Input(id=f"{field_id}-input")
            yield Static(_("Bans RIPOSTE simultanés au plus"), classes="omega-subtitle")
            yield Static(_("Au-delà, les nouvelles décisions de ban sont refusées par les garde-fous (visibles dans "
                           "Simuler et l'état)."), classes="omega-hint")
            yield Input(id="max-bans-input")
            yield Static(_("Exemptions RIPOSTE (réseaux)"), classes="omega-subtitle")
            yield Static(_("Jamais d'action RIPOSTE contre ces réseaux, séparés par des virgules (ex. 192.0.2.0/24)."),
                         classes="omega-hint")
            yield Input(placeholder=", ".join(_NETWORKS_EXAMPLE), id="exemptions-input")
            yield Static(_("Exclusions héritées du WAF (lecture seule)"), classes="omega-subtitle")
            yield Static("", id="waf-exclusions", classes="omega-hint")
            yield Static(_("Exemptions ajoutées par « Lever et exempter »"), classes="omega-subtitle")
            yield Static("", id="exemptions-error", classes="omega-hint")
            yield DataTable(id="exemptions-table", classes="omega-riposte-table")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retirer l'exemption"), id="remove-exemption", variant="error", disabled=True)
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer"), id="save", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#exemptions-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Réseau"), _("Jusqu'au"), _("Action d'origine"))
        self._refresh()

    def _refresh(self) -> None:
        config = self._load_riposte_config()
        if config is None:
            return
        riposte = riposte_config_of(config)
        show(self.query_one("#settings-module", Static),
            (_("Module : activé") if riposte_enabled(config) else _("Module : désactivé")) + " - "
            + _("activation dans Options (Configuration détaillée -> Options et vérification), redémarrage complet."))
        self.query_one("#tiers-input", Input).value = durations_text(riposte.tiers_seconds)
        self.query_one("#recidive-window-input", Input).value = duration_text(riposte.recidive_window_seconds)
        self.query_one("#episode-gap-input", Input).value = duration_text(riposte.episode_gap_seconds)
        self.query_one("#retention-input", Input).value = duration_text(riposte.history_retention_seconds)
        self.query_one("#max-bans-input", Input).value = str(riposte.max_active_bans)
        self.query_one("#exemptions-input", Input).value = ", ".join(riposte.exemptions)
        inherited = [n for n in riposte_exempt_networks(config, riposte) if n not in riposte.exemptions]
        show(self.query_one("#waf-exclusions", Static), ", ".join(inherited) or _("aucune"))
        self._refresh_exemptions()

    def _refresh_exemptions(self) -> None:
        self._selected_exemption = None
        self.query_one("#remove-exemption", Button).disabled = True
        table = self.query_one("#exemptions-table", DataTable)
        table.clear()
        config = self._load_riposte_config()
        if config is None:
            return
        try:
            with self._riposte_store(config) as store:
                exemptions = store.list_exemptions()
        except StoreUnavailable as error:
            show(self.query_one("#exemptions-error", Static), str(error))
            return
        show(self.query_one("#exemptions-error", Static), "" if exemptions else _("Aucune exemption ajoutée."))
        for exemption in exemptions:
            until = local_time(exemption.until) if exemption.until else _("retrait manuel")
            table.add_row(cell(exemption.network), cell(until), cell(exemption.origin_action_id or "-"), key=exemption.network)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_exemption = str(event.row_key.value)
        self.query_one("#remove-exemption", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "save":
            self._save()
        elif event.button.id == "remove-exemption" and self._selected_exemption is not None:
            network = self._selected_exemption
            self.app.push_screen(ConfirmScreen(
                title=_("RETIRER L'EXEMPTION"),
                message=_("RIPOSTE pourra de nouveau agir contre {network}. Continuer ?").format(network=network),
            ), lambda confirmed: self._remove_exemption(network, confirmed))

    def _remove_exemption(self, network: str, confirmed: bool | None) -> None:
        config = self._load_riposte_config() if confirmed else None
        if config is not None:
            self._send_commands(config, [("remove_exemption", {"network": network})], done=self._refresh_exemptions)

    def _value(self, field_id: str) -> str:
        return self.query_one(f"#{field_id}-input", Input).value

    def _save(self) -> None:
        error = self.query_one("#settings-error", Static)
        tiers = parse_durations(self._value("tiers"))
        durations = {field_id: parse_duration(self._value(field_id)) for field_id, _label, _hint in _DURATION_FIELDS}
        max_bans = self._value("max-bans").strip()
        if tiers is None or None in durations.values():
            show(error, _("Durée invalide : un nombre suivi de s, m, h ou d (ex. 6h, 30d)."))
            return
        if not max_bans.isdigit():
            show(error, _("Nombre invalide (entier positif attendu)."))
            return
        config = self._load_riposte_config()
        if config is None:
            return
        values = GlobalSettings(
            tiers_seconds=tiers, recidive_window_seconds=durations["recidive-window"] or 0,
            episode_gap_seconds=durations["episode-gap"] or 0, history_retention_seconds=durations["retention"] or 0,
            max_active_bans=int(max_bans),
            exemptions=tuple(n.strip() for n in self._value("exemptions").split(",") if n.strip()),
        )
        saved = save_global_settings(self._container.configuration, self._container.config_file, config, values)
        if not saved.ok:
            show(error, _("Non enregistré : ") + "; ".join(saved.errors))
            return
        show(error, "")
        self.app.notify(_("Réglages RIPOSTE enregistrés."))
        self._reload_riposte(config, done=self._refresh)
