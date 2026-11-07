"""Aide -> Contact et support (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b) : payer un cafe (PayPal), se
declarer utilisateur anonyme, contacter le support (mail et formulaire du site, aucun formulaire
dans omega-serv). Les adresses sont toujours affichees en clair : sans session graphique (SSH,
serveur), le navigateur ne s'ouvre pas et l'utilisateur les recopie."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.declaration.use_cases import (
    WithdrawResult,
    declaration_status,
    withdraw,
)
from omega_serv.application.updates.check_updates import check_for_update
from omega_serv.core.i18n import _
from omega_serv.domain.declaration.model import MODE_DAILY
from omega_serv.domain.updates.release_check import UpdateCheck, UpdateStatus
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.declaration_screen import DeclarationScreen, local_date

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

PAYPAL_URL = "https://paypal.me/kraynux"
SUPPORT_MAIL = "kraynux@proton.me"
CONTACT_FORM_URL = "https://kraynux.snake-mackarel.ts.net/contact/"


class ContactSupportScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._release_notes_url = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("CONTACT ET SUPPORT"), classes="omega-title")
            yield Static(_("Aidez le développeur : omega-serv est développé et maintenu par une seule personne."),
                         classes="omega-hint")

            yield Static(_("Payer un café"), classes="omega-subtitle")
            yield Static(_("Un don aide à couvrir les frais des serveurs (électricité)."), classes="omega-hint")
            yield Static(PAYPAL_URL)
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Payer un café"), id="coffee", variant="primary")

            yield Static(_("Se déclarer utilisateur (anonyme)"), classes="omega-subtitle")
            yield Static(_("Une déclaration volontaire et anonyme, qui sert uniquement à compter les utilisateurs "
                           "et, si vous le souhaitez, leur continent ou leur pays."), classes="omega-hint")
            yield Static("", id="declaration-state")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Se déclarer utilisateur (anonyme)"), id="declare", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ne plus me déclarer"), id="withdraw", variant="error", disabled=True)

            yield Static(_("Contacter le support"), classes="omega-subtitle")
            yield Static(_("Mail : {mail}").format(mail=SUPPORT_MAIL))
            yield Static(_("Formulaire de contact : {url}").format(url=CONTACT_FORM_URL))
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Contacter le support"), id="contact", variant="primary")

            # Verification manuelle des mises a jour (decision utilisateur 2026-11-07) : aucune connexion sans clic.
            yield Static(_("Version et mises à jour"), classes="omega-subtitle")
            yield Static(_("Compare votre version à la liste des versions publiées sur le site. Rien n'est envoyé, "
                           "et rien n'est vérifié sans votre clic."), classes="omega-hint")
            yield Static(_("Version installée : {version}").format(version=self._container.app_version),
                         id="update-state")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Vérifier les mises à jour"), id="check-update", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Voir les nouveautés"), id="release-notes", disabled=True)
        with Horizontal(classes="omega-actions omega-riposte-actions"), Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        status = declaration_status(self._container.declaration_store, os.environ)
        state = self.query_one("#declaration-state", Static)
        declare_button = self.query_one("#declare", Button)
        withdraw_button = self.query_one("#withdraw", Button)
        if status.declaration is None:
            state.update(_("État : non déclaré."))
            declare_button.label = _("Se déclarer utilisateur (anonyme)")
            withdraw_button.disabled = True
            return
        mode = _("chaque jour") if status.declaration.mode == MODE_DAILY else _("une seule fois")
        lines = [
            _("État : déclaré depuis le {date} (envoi : {mode}).").format(date=local_date(status.declared_at), mode=mode),
            _("Dernier envoi réussi : {date}").format(date=local_date(status.last_success)),
        ]
        if status.last_error:
            lines.append(_("Dernier essai : réception injoignable."))
        if status.do_not_track and status.declaration.mode == MODE_DAILY:
            lines.append(_("DO_NOT_TRACK est défini : aucun envoi automatique."))
        state.update("\n".join(lines))
        declare_button.label = _("Modifier ma déclaration")
        withdraw_button.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
        elif button_id == "coffee":
            self._open(PAYPAL_URL)
        elif button_id == "contact":
            self._open(CONTACT_FORM_URL)
        elif button_id == "check-update":
            self._check_update()
        elif button_id == "release-notes" and self._release_notes_url:
            self._open(self._release_notes_url)
        elif button_id == "declare":
            self.app.push_screen(DeclarationScreen(container=self._container), lambda _result: self._refresh())
        elif button_id == "withdraw":
            self.app.push_screen(ConfirmScreen(
                title=_("Ne plus me déclarer"),
                message=_("Votre entrée sera supprimée du compteur et la clé effacée de cette installation. "
                          "Continuer ?"),
            ), self._withdraw_if_confirmed)

    def _open(self, url: str) -> None:
        self.app.notify(_("Ouverture dans le navigateur..."))
        self.run_worker(lambda: self._open_in_thread(url), thread=True, exclusive=True)

    def _open_in_thread(self, url: str) -> None:
        opened = self._container.open_url(url)
        if not opened:
            self.app.call_from_thread(
                self.app.notify,
                _("Aucun navigateur disponible ici (session sans affichage) : ouvrez cette adresse vous-même : {url}")
                .format(url=url),
                severity="warning", timeout=15,
            )

    def _withdraw_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        sender = self._container.declaration_sender()
        if sender is None:
            self.app.notify(_("Envoi indisponible dans ce mode de lancement."), severity="error")
            return
        self.query_one("#withdraw", Button).disabled = True
        store = self._container.declaration_store
        self.run_worker(lambda: self.app.call_from_thread(self._finish_withdraw, withdraw(store, sender)),
                        thread=True, exclusive=True)

    def _finish_withdraw(self, result: WithdrawResult) -> None:
        if result.reception_reached:
            self.app.notify(_("Vous n'êtes plus déclaré : votre entrée est supprimée et la clé effacée."))
        else:
            self.app.notify(_("Clé effacée. Réception injoignable : votre entrée y disparaîtra seule "
                              "(90 jours en envoi quotidien, 1 an en envoi unique)."), severity="warning", timeout=12)
        self._refresh()

    def _check_update(self) -> None:
        source = self._container.release_source()
        if source is None:
            self.app.notify(_("Vérification indisponible dans ce mode de lancement."), severity="error")
            return
        self.query_one("#check-update", Button).disabled = True
        self.query_one("#update-state", Static).update(_("Vérification en cours..."))
        installed = self._container.app_version
        self.run_worker(lambda: self.app.call_from_thread(self._show_update, check_for_update(source, installed)),
                        thread=True, exclusive=True)

    def _show_update(self, check: UpdateCheck) -> None:
        try:
            state = self.query_one("#update-state", Static)
            notes = self.query_one("#release-notes", Button)
            self.query_one("#check-update", Button).disabled = False
        except NoMatches:
            return  # ecran deja ferme
        self._release_notes_url = ""
        notes.disabled = True
        if check.status is UpdateStatus.UPDATE_AVAILABLE:
            self._release_notes_url = check.notes_url
            notes.disabled = False
            state.update(_("Nouvelle version disponible : {latest} (installée : {installed}).\nArchive : {url}").format(
                latest=check.latest, installed=check.installed, url=check.archive_url))
        elif check.status is UpdateStatus.UP_TO_DATE:
            state.update(_("Vous avez la dernière version publiée ({version}).").format(version=check.installed))
        elif check.status is UpdateStatus.AHEAD:
            state.update(_("Votre version ({installed}) est plus récente que la dernière publiée ({latest}) : "
                           "version en cours, pas encore publiée.").format(installed=check.installed, latest=check.latest))
        else:
            state.update(_("Version installée : {version}. Site injoignable ou liste des versions illisible : "
                           "réessayez plus tard.").format(version=check.installed))
