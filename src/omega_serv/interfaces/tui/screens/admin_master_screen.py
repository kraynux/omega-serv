"""Ecran « Maître » : l'instance maitre acceptee par cette instance (tableau de bord web, lot 6 ;
OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §7.1 et §7.3 ; decisions de l'auteur du 2026-11-16, Q9 a Q11).

Ouvert depuis Instances -> Configuration distante -> Maître. Un seul maitre accepte, avec des droits fixes ici
(lecture ou administration) ; en accepter un autre remplace et revoque l'ancien (confirmation). Deux chemins :
« Relier au maitre » de l'ecran Instances (maitre sur cette machine, rien a recopier ; 2026-11-16 : omega-connect
plus tard) ou un code d'appairage a saisir sur le maitre, valable 10 minutes, une
seule fois, 3 essais faux ferment la fenetre. Le code et le temps restant s'affichent ici, mis a jour chaque
seconde."""
from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Select, Static

from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.master import display_pairing_code
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.link_master_dialog import rights_choices

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _rights_text(rights: str) -> str:
    return {"lecture": _("lecture"), "administration": _("administration")}.get(rights, rights)


def _local(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso or "-"


class AdminMasterScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._manager = container.admin_master_manager()

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("ADMINISTRATION WEB - MAÎTRE"), classes="omega-title")
            yield Static(_("Une instance maître peut suivre cette instance depuis son tableau de bord web, et la "
                           "piloter si vous lui donnez le droit d'administration. Un seul maître à la fois : en "
                           "accepter un autre remplace et révoque l'ancien."), classes="omega-hint")
            yield Static(_("Maître accepté"), classes="omega-subtitle")
            yield Static("", id="master-state")
            yield Static(_("Accepter un maître"), classes="omega-subtitle")
            yield Static(_("Maître sur cette machine : écran Instances -> « Relier au maître », rien à recopier. "
                           "Maître sur une autre machine : ouvrez une fenêtre d'appairage ici, puis sur le maître : "
                           "page Instances -> « Ajouter à la main » -> adresse, port et code. L'adresse du maître doit "
                           "être dans les réseaux permis (Configuration distante)."), classes="omega-hint")
            yield Static(_("Droits donnés au maître"), classes="omega-subtitle")
            yield Select(rights_choices(), allow_blank=False, value="lecture", id="rights-select")
            yield Static("", id="pairing-state")
            yield Static("", id="master-message", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Accepter un maître (code)"), id="open-pairing", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Fermer la fenêtre"), id="close-pairing", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Révoquer"), id="revoke", variant="error", disabled=True)
        with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(1.0, self._refresh)

    def _refresh(self) -> None:
        master = self._manager.master()
        if master is None:
            text = _("Aucun : cette instance n'est suivie par aucune autre.")
        else:
            text = "\n".join((
                _("Nom : {name}").format(name=master.master_name),
                _("Droits : {rights}").format(rights=_rights_text(master.rights)),
                _("Depuis : {since}").format(since=_local(master.since)),
                _("Dernier appel : {last}").format(last=_local(master.last_call) if master.last_call else "-"),
            ))
        self.query_one("#master-state", Static).update(text)
        window = self._manager.pairing()
        if window is None:
            pairing = ""
        else:
            left = max(0, int(window.expires_at - time.time()))
            pairing = _("Fenêtre d'appairage ouverte - code : {code}   (droits : {rights}, encore {minutes} min "
                        "{seconds:02d} s)").format(code=display_pairing_code(window.code),
                                                   rights=_rights_text(window.rights), minutes=left // 60,
                                                   seconds=left % 60)
        self.query_one("#pairing-state", Static).update(pairing)
        self.query_one("#close-pairing", Button).disabled = window is None
        self.query_one("#revoke", Button).disabled = master is None

    def _message(self, text: str) -> None:
        self.query_one("#master-message", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "back":
            self.dismiss()
        elif button == "open-pairing":
            master = self._manager.master()
            if master is None:
                self._open_pairing(True)
            else:
                self.app.push_screen(ConfirmScreen(title=_("REMPLACER LE MAÎTRE"), message=_(
                    "{name} est le maître accepté. À la fin de l'appairage, le nouveau maître le remplacera et "
                    "{name} sera révoqué aussitôt. Continuer ?").format(name=master.master_name)),
                    self._open_pairing)
        elif button == "close-pairing":
            self._manager.close_pairing()
            self._message(_("Fenêtre d'appairage fermée."))
            self._refresh()
        elif button == "revoke":
            master = self._manager.master()
            if master is not None:
                self.app.push_screen(ConfirmScreen(title=_("RÉVOQUER LE MAÎTRE"), message=_(
                    "Révoquer {name} ? Ses appels sont refusés dès maintenant ; le suivre de nouveau demandera un "
                    "nouvel appairage.").format(name=master.master_name)), self._revoke)

    def _open_pairing(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        rights = str(self.query_one("#rights-select", Select).value)
        outcome = self._manager.open_pairing(rights, replace_existing=True)
        self._message(_("Saisissez ce code sur le maître dans les 10 minutes.") if outcome.ok else _(
            "Écriture impossible dans var/lib/admin (droits du dossier)."))
        self._refresh()

    def _revoke(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        name = self._manager.revoke()
        self._message(_("Maître révoqué : {name}. Ses appels sont refusés dès maintenant.").format(name=name)
                      if name else _("Aucun maître accepté."))
        self._refresh()
