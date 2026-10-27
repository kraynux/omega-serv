"""Ecran Detail d'une capacite (plan interface §5) - identifiant,
statut, raison, details techniques, dernier scan. Recoit le registre
deja scanne par CapabilitiesScreen (jamais un second scan - le detail
doit refleter exactement ce que la liste affichait au moment du clic)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.capability import CapabilityStatus
from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.core.capability_registry import CapabilityRegistry

_DIRECTIVES: dict[CapabilityStatus, str] = {
    CapabilityStatus.AVAILABLE: _("Cette capacité est pleinement opérationnelle et disponible."),
    CapabilityStatus.DEGRADED: _("Capacité partiellement fonctionnelle - vérifiez la configuration associée."),
    CapabilityStatus.MISSING: _("Composant non détecté - installez ou configurez l'élément requis si nécessaire."),
    CapabilityStatus.DISQUALIFIED: _("Capacité disqualifiée - un problème réel a été détecté, à corriger."),
}


class CapabilityDetailScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, registry: CapabilityRegistry, capability_id: str) -> None:
        super().__init__()
        self._container = container
        self._registry = registry
        self._capability_id = capability_id

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("DÉTAIL D'UNE CAPACITÉ"), classes="omega-title")
            yield Static("", id="detail-body")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        body = self.query_one("#detail-body", Static)
        cap = self._registry.get(self._capability_id)
        if cap is None:
            body.update(_("Capacité '{capability_id}' introuvable dans le registre.").format(capability_id=self._capability_id))
            return

        lines = [
            _("[b]Identifiant :[/b] {id}").format(id=cap.id),
            _("[b]Categorie :[/b] {value}").format(value=cap.category or '-'),
            _("[b]Statut actuel :[/b] {value}").format(value=cap.status.value.upper()),
        ]
        if cap.reason:
            lines.append(_("[b]Raison :[/b] {reason}").format(reason=cap.reason))
        if cap.detail:
            lines.append(_("[b]Details techniques :[/b] {detail}").format(detail=cap.detail))
        lines.append(_("[b]Dernier scan :[/b] {value}").format(value=cap.last_checked.strftime('%Y-%m-%d %H:%M:%S')))
        lines.append("")
        lines.append(_DIRECTIVES.get(cap.status, ""))
        body.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
