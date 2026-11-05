"""Aide -> Contact et support -> Se declarer utilisateur (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b.2).

Formulaire anonyme : mode d'envoi (aucun preselectionne), continent et pays facultatifs (deux
listes independantes, chacune avec « Autre »), puis le message EXACT qui sera envoye, mis a jour a
chaque choix. L'envoi tourne dans un fil de travail : l'ecran ne se fige jamais (5 s au plus)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Select, Static

from omega_serv.application.declaration.use_cases import DeclareResult, declare, preview_payload
from omega_serv.core.i18n import N_, STATE, _
from omega_serv.domain.declaration.countries import COUNTRY_CODES
from omega_serv.domain.declaration.model import (
    MODE_DAILY,
    MODE_ONCE,
    OTHER,
    RECEPTION_URL,
    do_not_track,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_CONTINENT_LABELS = (
    ("AF", N_("Afrique")),
    ("AN", N_("Antarctique")),
    ("AS", N_("Asie")),
    ("EU", N_("Europe")),
    ("NA", N_("Amérique du Nord")),
    ("OC", N_("Océanie")),
    ("SA", N_("Amérique du Sud")),
)


def local_date(value: datetime | None) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M") if value is not None else "-"


@cache
def _country_names() -> dict[str, dict[str, str]]:
    data = resources.files("omega_serv.domain.declaration").joinpath("country_names.json").read_text(encoding="utf-8")
    names = json.loads(data)["names"]
    return names if isinstance(names, dict) else {}


def country_options(language_code: str) -> list[tuple[str, str]]:
    """(libelle, code) tries par nom dans la langue de l'interface ; « Autre » en dernier. Langue
    sans table (langue de controle) : noms francais."""
    names = _country_names()
    table = names.get(language_code) or names.get("fr") or {}
    options = sorted(((table.get(code, code), code) for code in COUNTRY_CODES), key=lambda item: item[0].casefold())
    return [*options, (_("Autre (non référencé)"), OTHER)]


def continent_options() -> list[tuple[str, str]]:
    return [*((_(label), code) for code, label in _CONTINENT_LABELS), (_("Autre (non référencé)"), OTHER)]


class DeclarationScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._existing = container.declaration_store.load()

    def compose(self) -> ComposeResult:
        existing = self._existing.declaration if self._existing is not None else None
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("SE DÉCLARER UTILISATEUR (ANONYME)"), classes="omega-title")
            yield Static(_("Une déclaration volontaire et anonyme : elle sert uniquement à compter les utilisateurs "
                           "d'omega-serv et, si vous le souhaitez, leur continent ou leur pays. Une clé tirée au "
                           "hasard est créée pour cette installation ; elle n'a aucun lien avec vous ni avec votre "
                           "machine."), classes="omega-hint")

            yield Static(_("Envoi"), classes="omega-subtitle")
            yield Static(_("Une seule fois : un envoi maintenant. Chaque jour : le serveur envoie le même message "
                           "une fois par jour, ce qui permet de compter les installations actives."),
                         classes="omega-hint")
            yield Select([(_("Une seule fois"), MODE_ONCE), (_("Chaque jour"), MODE_DAILY)],
                         value=existing.mode if existing else Select.NULL, allow_blank=True,
                         prompt=_("Choisir..."), id="declaration-mode")
            yield Static("", id="declaration-dnt", classes="omega-hint")

            yield Static(_("Continent (facultatif)"), classes="omega-subtitle")
            yield Select(continent_options(), value=existing.continent if existing and existing.continent else Select.NULL,
                         allow_blank=True, prompt=_("Non précisé"), id="declaration-continent")
            yield Static(_("Pays (facultatif)"), classes="omega-subtitle")
            yield Select(country_options(STATE.language.code),
                         value=existing.country if existing and existing.country else Select.NULL,
                         allow_blank=True, prompt=_("Non précisé"), id="declaration-country")

            yield Static(_("Message envoyé"), classes="omega-subtitle")
            yield Static("", id="declaration-preview")
            yield Static(_("Destination : {url}").format(url=RECEPTION_URL), classes="omega-hint")
            yield Static(_("Jamais envoyés : votre nom, le nom de la machine, le contenu de votre site, vos journaux."),
                         classes="omega-hint")
            yield Static(_("Votre adresse IP n'est pas enregistrée dans les déclarations. Comme pour toute visite "
                           "d'un site, elle passe par les contrôles de sécurité et le journal technique du serveur "
                           "de réception."), classes="omega-hint")
            yield Static(_("Vous pouvez retirer votre déclaration à tout moment depuis Contact et support."),
                         classes="omega-hint")
            yield Static("", id="declaration-error", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Envoyer"), id="send", variant="primary", disabled=existing is None)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Annuler"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._update_preview()

    def _value(self, widget_id: str) -> str:
        value = self.query_one(f"#{widget_id}", Select).value
        return "" if value is Select.NULL or value is None else str(value)

    def on_select_changed(self, _event: Select.Changed) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        mode = self._value("declaration-mode")
        self.query_one("#send", Button).disabled = not mode
        dnt = do_not_track(os.environ) and mode == MODE_DAILY
        self.query_one("#declaration-dnt", Static).update(
            _("DO_NOT_TRACK est défini : « chaque jour » n'enverra rien automatiquement.") if dnt else "")
        if not mode:
            self.query_one("#declaration-preview", Static).update(_("(choisissez d'abord le mode d'envoi)"))
            return
        payload = preview_payload(self._container.declaration_store, self._container.app_version, mode,
                                  self._value("declaration-continent"), self._value("declaration-country"))
        if self._existing is None:
            payload["cle"] = _("<clé tirée au hasard à l'envoi>")
        self.query_one("#declaration-preview", Static).update(json.dumps(payload, ensure_ascii=False))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "send":
            self._send()

    def _send(self) -> None:
        mode = self._value("declaration-mode")
        if not mode:
            return
        sender = self._container.declaration_sender()
        if sender is None:
            self.query_one("#declaration-error", Static).update(_("Envoi indisponible dans ce mode de lancement."))
            return
        continent, country = self._value("declaration-continent"), self._value("declaration-country")
        container = self._container
        self.query_one("#send", Button).disabled = True
        self.query_one("#declaration-error", Static).update(_("Envoi en cours..."))

        def run() -> None:
            result = declare(container.declaration_store, sender, container.clock, container.app_version,
                             mode, continent, country)
            self.app.call_from_thread(self._finish, result)

        self.run_worker(run, thread=True, exclusive=True)

    def _finish(self, result: DeclareResult) -> None:
        if result.ok:
            self.app.notify(_("Merci ! Vous êtes déclaré utilisateur anonyme."))
            self.dismiss()
            return
        self.query_one("#send", Button).disabled = False
        if result.recorded:
            self.app.notify(_("Réception injoignable : votre accord est gardé, le serveur réessaiera dans 24 h."),
                            severity="warning", timeout=12)
            self.dismiss()
            return
        self.query_one("#declaration-error", Static).update(
            _("Réception injoignable : rien n'a été enregistré, réessayez plus tard."))
