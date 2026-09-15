# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de generation du rapport local d'un incident
(plan_active_defense_omega_serv.md, Phase 0/2) - Markdown local, jamais
un envoi distant."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.security.active_defense.entities import ExportResult, Incident


class IncidentReportExporterPort(Protocol):
    def render(self, incident: Incident) -> ExportResult:
        ...
