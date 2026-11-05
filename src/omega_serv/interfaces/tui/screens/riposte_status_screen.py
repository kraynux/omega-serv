"""RIPOSTE - Etat (topo §6.4-1, §6.6 ; lot 5) : module, processus, arret d'urgence, actions en cours,
lecture des journaux, decisions ; boutons Rafraichir, Arret d'urgence (ou Reprendre), Retour.

Arret d'urgence (topo §6.6) : confirmation avec le nombre d'actions en cours et le choix [Arreter et
lever les actions en cours] [Arreter seulement] [Annuler] ; l'ecran dit ce que l'arret ne touche pas.
Le drapeau est pose directement (persistant, respecte meme processus arrete) ; « Reprendre » remplace le
bouton tant qu'il est actif."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.riposte.console import (
    emergency_stop,
    process_running,
    resume,
    riposte_config_of,
    riposte_enabled,
    waf_enabled,
)
from omega_serv.application.riposte.get_status import get_riposte_status
from omega_serv.core.i18n import _
from omega_serv.domain.security.riposte.network_ban import JAIL_DURATIONS
from omega_serv.interfaces.cli.riposte_text import format_status
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._riposte_access import (
    RiposteAccessMixin,
    StoreUnavailable,
    show,
)
from omega_serv.interfaces.tui.screens.choice_screen import Choice, ChoiceResult, ChoiceScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.security.riposte.config import RiposteConfig


class RiposteStatusScreen(RiposteAccessMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._stopped = False
        self._in_progress = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RIPOSTE - ÉTAT"), classes="omega-title")
            yield Static(
                _("L'activation du module 'riposte' se fait dans le menu Options (Configuration détaillée -> "
                  "Options et vérification) et demande un redémarrage complet du service."),
                classes="omega-hint",
            )
            yield Static("", id="riposte-module", classes="omega-subtitle")
            yield Static("", id="riposte-warnings", classes="omega-hint")
            yield Static("", id="riposte-status-body")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rafraîchir"), id="refresh")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Arrêt d'urgence"), id="emergency-stop", variant="error")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        body = self.query_one("#riposte-status-body", Static)
        config = self._load_riposte_config()
        if config is None:
            return
        riposte = riposte_config_of(config)
        active = sum(1 for p in riposte.policies if p.enabled)
        show(self.query_one("#riposte-module", Static),
            (_("Module : activé") if riposte_enabled(config) else _("Module : désactivé")) + " - "
            + _("politiques actives : {active} sur {total}").format(active=active, total=len(riposte.policies)))
        warnings = []
        if not waf_enabled(config):
            warnings.append(_("Activer le WAF pour les actions de ban : sans WAF, RIPOSTE ne voit aucune attaque."))
        if not riposte.policies:
            warnings.append(_("Aucune politique : RIPOSTE observe sans jamais agir (écran Politiques)."))
        warnings += self._network_warnings(config, riposte)
        show(self.query_one("#riposte-warnings", Static), "\n".join(warnings))
        try:
            with self._riposte_store(config) as store:
                status = get_riposte_status(store, self._container.clock.now())
                self._in_progress = store.count_in_progress(bans_only=False)
                bans = store.count_in_progress(bans_only=True)
                network = sum(1 for a in store.list_actions(in_progress=True, limit=10_000)
                              if a.kind == "local_and_network_ban")
        except StoreUnavailable as error:
            show(body, str(error))
            self._set_stop_button(stopped=False)
            return
        lines = format_status(status, self._in_progress, bans)
        if network:
            lines.append(_("Bans réseau passés à fail2ban : {count} (à lever dans omega-jail ou fail2ban).").format(count=network))
        show(body, "\n".join(lines))
        self._set_stop_button(stopped=status.emergency_stop)

    def _network_warnings(self, config: OmegaServConfig, riposte: RiposteConfig) -> list[str]:
        """Ban reseau (topo §7.1-4) : jails RIPOSTE de cette instance installees ou non, et la jail Active Defense
        a ban fixe de 24 h, redondante, qui ecrase les paliers reseau."""
        if not any(p.enabled and p.action == "local_and_network_ban" for p in riposte.policies):
            return []
        if not riposte.network_ban_log:
            return [_("Ban réseau désactivé (network_ban_log) : seules les parties locales des bans s'appliquent.")]
        service = self._service_name()
        expected = [f"{service}-riposte-{suffix}" for _seconds, suffix in JAIL_DURATIONS]
        reader = self._container.installed_jails_reader
        installed = reader() if reader is not None else None
        if installed is None:
            return [_("Jails du ban réseau : fail2ban absent ou illisible - jails attendues : {jails}.").format(
                jails=", ".join(expected))]
        lines = []
        missing = [name for name in expected if name not in installed]
        if missing:
            lines.append(_("Jails du ban réseau absentes : {jails} - les installer avec omega-jail.").format(
                jails=", ".join(missing)))
        else:
            lines.append(_("Jails du ban réseau installées : {jails}.").format(jails=", ".join(expected)))
        if "omega-serv-active-defense" in installed:
            lines.append(_("La jail omega-serv-active-defense (ban fixe de 24 h) écrase les paliers réseau de RIPOSTE : "
                           "la désactiver dans omega-jail."))
        return lines

    def _set_stop_button(self, *, stopped: bool) -> None:
        self._stopped = stopped
        button = self.query_one("#emergency-stop", Button)
        button.label = _("Reprendre") if stopped else _("Arrêt d'urgence")
        button.variant = "primary" if stopped else "error"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "refresh":
            self._refresh()
        elif event.button.id == "emergency-stop":
            if self._stopped:
                self._resume()
            else:
                self._ask_emergency_stop()

    def _ask_emergency_stop(self) -> None:
        message = "\n\n".join((
            _("Plus aucune nouvelle action, pour toutes les règles, même après un redémarrage, jusqu'à « Reprendre ». "
              "Actions en cours : {count}.").format(count=self._in_progress),
            _("« Arrêter seulement » : elles vont jusqu'à leur échéance. « Lever » : retrait de la blocklist et "
              "libération des leurres tout de suite."),
            _("Non touchés : les bans automatiques du WAF et le mode guerre d'Active Defense (hors RIPOSTE), les bans "
              "réseau déjà passés à fail2ban par omega-jail (à lever dans omega-jail ou fail2ban)."),
        ))
        self.app.push_screen(ChoiceScreen(
            title=_("ARRÊT D'URGENCE DE RIPOSTE"), message=message,
            choices=[
                Choice("revoke", _("Arrêter et lever les actions en cours"), "error"),
                Choice("stop", _("Arrêter seulement"), "error"),
                Choice("cancel", _("Annuler"), "primary"),
            ],
        ), self._emergency_stop_chosen)

    def _emergency_stop_chosen(self, result: ChoiceResult | None) -> None:
        if result is None:
            return
        config = self._load_riposte_config()
        if config is None:
            return
        try:
            with self._riposte_store(config, write=True) as store:
                now = self._container.clock.now()
                ids = emergency_stop(store, now, revoke=result.choice == "revoke")
                running = process_running(store, now)
        except (StoreUnavailable, OSError) as error:
            self.app.notify(str(error), severity="error")
            return
        self.app.notify(_("Arrêt d'urgence ACTIF : aucune nouvelle action, même après un redémarrage, jusqu'à "
                          "« Reprendre »."), severity="warning")
        self._refresh()
        self._after_deposit(config, ids, running, self._refresh)

    def _resume(self) -> None:
        config = self._load_riposte_config()
        if config is None:
            return
        try:
            with self._riposte_store(config, write=True) as store:
                resume(store, self._container.clock.now())
        except (StoreUnavailable, OSError) as error:
            self.app.notify(str(error), severity="error")
            return
        self.app.notify(_("Arrêt d'urgence levé : RIPOSTE reprend ses décisions."))
        self._refresh()
