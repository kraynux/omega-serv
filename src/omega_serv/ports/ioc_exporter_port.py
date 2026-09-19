"""Contrat d'export des IoC d'un incident (plan_active_defense_omega_
serv.md, Phase 0/2) - JSON/CSV/Markdown, jamais un envoi distant
automatique (voir "Configuration et activation" du plan)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.security.active_defense.entities import ExportResult, Incident


class IoCExporterPort(Protocol):
    def export(self, incident: Incident) -> ExportResult:
        ...
