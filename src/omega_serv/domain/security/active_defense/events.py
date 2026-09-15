# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Evenements metier Active Defense (plan_active_defense_omega_serv.md,
Phase 0) - produits par les politiques/cas d'usage quand une action est
justifiee, jamais des effets de bord eux-memes (l'ecriture au journal
d'audit, la creation reelle d'un incident etc. restent des
responsabilites de l'application/infrastructure qui consomment ces
evenements)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from omega_serv.domain.security.active_defense.value_objects import ThreatLevel


@dataclass(frozen=True)
class ThreatEscalated:
    subject_id: str
    previous_level: ThreatLevel
    new_level: ThreatLevel
    occurred_at: datetime


@dataclass(frozen=True)
class DeceptionAssigned:
    subject_id: str
    profile_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class EnhancedLoggingRequested:
    subject_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class IncidentOpened:
    incident_id: str
    subject_id: str
    occurred_at: datetime
