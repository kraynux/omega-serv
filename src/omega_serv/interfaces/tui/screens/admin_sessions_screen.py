"""Sessions ouvertes du panneau web, vues depuis la TUI (etude modules, module 5, 2026-11-17) : liste publiee par le
processus d'administration toutes les 5 s (sans jeton) ; « Fermer » depose une demande qu'il applique a son tour
suivant. Ouvert depuis Instances -> Configuration distante -> Comptes -> Sessions."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Select, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

STALE_SECONDS = 30


class AdminSessionsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("ADMINISTRATION WEB - SESSIONS OUVERTES"), classes="omega-title")
            yield Static(_("Navigateurs connectés au panneau web. Fermer une session déconnecte ce navigateur dans les "
                           "5 secondes ; c'est noté dans le journal d'audit."), classes="omega-hint")
            yield Static("", id="sessions-text")
            yield Static(_("Session à fermer"), classes="omega-subtitle")
            yield Select([], id="sessions-select", prompt=_("Choisir une session"))
        with Horizontal(classes="omega-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Fermer la session"), id="close", variant="error")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rafraîchir"), id="refresh")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._show()

    def _show(self) -> None:
        published = self._container.admin_session_files().published()
        text = self.query_one("#sessions-text", Static)
        select = self.query_one("#sessions-select", Select)
        if published is None:
            text.update(_("Aucune liste publiée : l'administration web n'est pas lancée."))
            select.set_options([])
            return
        stamp, sessions = published
        lines, options = [], []
        for item in sessions:
            opened = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(item.get("ouverte", 0))))
            seen = time.strftime("%H:%M", time.localtime(float(item.get("activite", 0))))
            label = _("{account} depuis {address}, ouverte le {opened}, active à {seen}").format(
                account=item.get("compte", "?"), address=item.get("adresse") or "-", opened=opened, seen=seen)
            lines.append("• " + label)
            options.append((label, str(item.get("id", ""))))
        if time.time() - stamp > STALE_SECONDS:
            lines.append(_("Liste du {date} : l'administration web semble arrêtée.").format(
                date=time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp))))
        text.update("\n".join(lines) or _("Aucune session ouverte."))
        select.set_options(options)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "refresh":
            self._show()
        elif event.button.id == "close":
            value = self.query_one("#sessions-select", Select).value
            if not isinstance(value, str) or not value:
                self.app.notify(_("Choisissez d'abord une session."), severity="warning")
                return
            self._container.admin_session_files().request_close(value)
            self.app.notify(_("Demande envoyée : la session sera fermée dans les 5 secondes."))
