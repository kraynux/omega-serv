"""Active Securite -> INTERVENTION MANUELLE -> Bannir (decisions utilisateur 2026-11-06) : ban SANS CONDITION d'une
seule adresse IP dans la blocklist du WAF (page 451 avant tout routage). Aucune regle, aucun seuil, aucun lien avec
Active Defense ni RIPOSTE. Un reseau est refuse : il se bannit dans WAF -> Modules -> Liste de blocage.

Confirmation demandee (une seule boite, tous les avertissements) : adresse locale/privee/Tailscale, ban existant
d'une autre origine remplace, ban permanent."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Select, Static

from omega_serv.application.security.manual_intervention import (
    NETWORK_HINT,
    ban_address,
    check_ban_request,
    protected_networks,
    waf_enabled,
)
from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._intervention_access import (
    BlocklistUnavailable,
    open_blocklist,
)
from omega_serv.interfaces.tui.screens._riposte_access import show
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_HOUR = 3600
_FREE = "free"
_PERMANENT = "permanent"
_DURATIONS: tuple[tuple[str, str], ...] = (
    (_("1 heure"), str(_HOUR)),
    (_("6 heures"), str(6 * _HOUR)),
    (_("24 heures"), str(24 * _HOUR)),
    (_("7 jours"), str(7 * 24 * _HOUR)),
    (_("30 jours"), str(30 * 24 * _HOUR)),
    (_("Durée libre (heures)"), _FREE),
    (_("Permanent"), _PERMANENT),
)


class ManualBanScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("BANNIR UNE ADRESSE IP"), classes="omega-title")
            yield Static(
                _("Ban sans condition : l'adresse reçoit la page 451 sur tout le site, avant les backends. Aucun lien "
                  "avec Active Defense ni RIPOSTE (jamais compté dans la récidive) ; il se lève dans Débannir."),
                classes="omega-hint",
            )
            yield Static(NETWORK_HINT, classes="omega-hint")
            yield Static("", id="waf-warning", classes="omega-hint")
            yield Static("", id="ban-error", classes="omega-hint")
            yield Static(_("Adresse IP"), classes="omega-subtitle")
            yield Input(placeholder=_("ex. 203.0.113.7 ou 2001:db8::7"), id="ban-ip")
            yield Static(_("Motif du ban"), classes="omega-subtitle")
            yield Input(placeholder=_("Intervention manuelle"), id="ban-reason")
            yield Static(_("Durée"), classes="omega-subtitle")
            yield Select(_DURATIONS, value=str(24 * _HOUR), allow_blank=False, id="ban-duration")
            yield Static(_("Durée libre (heures)"), classes="omega-subtitle")
            yield Input(placeholder=_("ex. 48"), id="ban-hours", disabled=True)
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Bannir"), id="ban", variant="error")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        try:
            config, _port = open_blocklist(self._container)
        except BlocklistUnavailable as problem:
            show(self.query_one("#ban-error", Static), str(problem))
            return
        show(self.query_one("#waf-warning", Static), "" if waf_enabled(config) else _(
            "WAF désactivé : la blocklist n'est pas consultée, un ban posé ici n'aurait aucun effet. Activez "
            "l'option waf (menu Options)."))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "ban-duration":
            self.query_one("#ban-hours", Input).disabled = event.value != _FREE

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "ban":
            self._request_ban()

    def _duration(self) -> tuple[bool, int | None]:
        """(valide, secondes ; None = permanent)."""
        choice = str(self.query_one("#ban-duration", Select).value)
        if choice == _PERMANENT:
            return True, None
        if choice != _FREE:
            return True, int(choice)
        text = self.query_one("#ban-hours", Input).value.strip()
        if not text.isdigit() or int(text) <= 0:
            return False, None
        return True, int(text) * _HOUR

    def _request_ban(self) -> None:
        error = self.query_one("#ban-error", Static)
        valid, duration = self._duration()
        if not valid:
            show(error, _("Durée libre invalide : un nombre d'heures entier, supérieur à 0."))
            return
        try:
            config, port = open_blocklist(self._container)
        except BlocklistUnavailable as problem:
            show(error, str(problem))
            return
        check = check_ban_request(port, self.query_one("#ban-ip", Input).value, duration is None,
                                  protected_networks(config), self._container.clock.now())
        if check.network is None:
            show(error, check.error)
            return
        show(error, "")
        network = check.network
        if not check.warnings:
            self._ban(network, duration)
            return
        self.app.push_screen(
            ConfirmScreen(title=_("Confirmer le ban de {ip}").format(ip=network.split("/")[0]),
                          message="\n\n".join(check.warnings)),
            lambda confirmed: self._ban(network, duration) if confirmed else None,
        )

    def _ban(self, network: str, duration: int | None) -> None:
        try:
            _config, port = open_blocklist(self._container)
        except BlocklistUnavailable as problem:
            show(self.query_one("#ban-error", Static), str(problem))
            return
        result = ban_address(port, network, self.query_one("#ban-reason", Input).value, duration,
                             self._container.clock.now())
        show(self.query_one("#ban-error", Static), "" if result.success else result.message)
        self.app.notify(result.message, severity="information" if result.success else "error")
        if result.success:
            self.query_one("#ban-ip", Input).value = ""
