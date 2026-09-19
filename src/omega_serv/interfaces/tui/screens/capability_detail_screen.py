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
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.core.capability_registry import CapabilityRegistry

_DIRECTIVES: dict[CapabilityStatus, str] = {
    CapabilityStatus.AVAILABLE: "Cette capacite est pleinement operationnelle et disponible.",
    CapabilityStatus.DEGRADED: "Capacite partiellement fonctionnelle - verifiez la configuration associee.",
    CapabilityStatus.MISSING: "Composant non detecte - installez ou configurez l'element requis si necessaire.",
    CapabilityStatus.DISQUALIFIED: "Capacite disqualifiee - un probleme reel a ete detecte, a corriger.",
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
            yield Static("DETAIL D'UNE CAPACITE", classes="omega-title")
            yield Static("", id="detail-body")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        body = self.query_one("#detail-body", Static)
        cap = self._registry.get(self._capability_id)
        if cap is None:
            body.update(f"Capacite '{self._capability_id}' introuvable dans le registre.")
            return

        lines = [
            f"[b]Identifiant :[/b] {cap.id}",
            f"[b]Categorie :[/b] {cap.category or '-'}",
            f"[b]Statut actuel :[/b] {cap.status.value.upper()}",
        ]
        if cap.reason:
            lines.append(f"[b]Raison :[/b] {cap.reason}")
        if cap.detail:
            lines.append(f"[b]Details techniques :[/b] {cap.detail}")
        lines.append(f"[b]Dernier scan :[/b] {cap.last_checked.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(_DIRECTIVES.get(cap.status, ""))
        body.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
