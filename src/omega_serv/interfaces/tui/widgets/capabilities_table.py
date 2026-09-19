"""Tableau des capacites systeme (plan interface §5, menu 1) - une ligne
par capacite, statut colore. Couleurs resolues via
`App.get_css_variables()` (jetons de palette omega-lib deja enregistres
par `build_all_textual_themes()`, `$success`/`$warning`/`$error`) plutot
qu'une extension de theme dediee comme omega-fire (`theme_extensions.py`,
4 jetons `$status-*` propres a fire) - SERV n'a que 4 statuts a
distinguer et la palette generique en couvre deja 3 sur 4 sans rien
ajouter (MISSING utilise le premier plan attenue, meme convention que
`.omega-hint`)."""
from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import DataTable

from omega_serv.core.capability import Capability, CapabilityStatus

_STATUS_LABELS: dict[CapabilityStatus, str] = {
    CapabilityStatus.AVAILABLE: "DISPONIBLE",
    CapabilityStatus.DEGRADED: "DEGRADE",
    CapabilityStatus.MISSING: "MANQUANT",
    CapabilityStatus.DISQUALIFIED: "DISQUALIFIE",
}

_STATUS_VARIABLE: dict[CapabilityStatus, str] = {
    CapabilityStatus.AVAILABLE: "success",
    CapabilityStatus.DEGRADED: "warning",
    CapabilityStatus.DISQUALIFIED: "error",
}


class CapabilitiesTable(DataTable[Any]):
    """Une ligne par capacite systeme, statut colore."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Statut", "Categorie", "Capacite", "Raison")

    def set_capabilities(self, capabilities: tuple[Capability, ...]) -> None:
        self.clear()
        variables = self.app.get_css_variables()
        for cap in capabilities:
            variable = _STATUS_VARIABLE.get(cap.status)
            color = variables.get(variable, "") if variable is not None else ""
            style = f"bold {color}" if color else "dim"
            badge = Text(_STATUS_LABELS[cap.status], style=style)
            self.add_row(badge, cap.category or "-", cap.id, cap.reason or "-", key=cap.id)
