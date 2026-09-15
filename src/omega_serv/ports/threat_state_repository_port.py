# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de persistance de l'etat de menace par source
(plan_active_defense_omega_serv.md, Phase 0). `instance_id` absent des
signatures - chaque process OMEGA-SERV a sa propre base locale, le
cloisonnement par instance est deja garanti par des fichiers separes
(voir "Ports applicatifs" du plan)."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from omega_serv.domain.security.active_defense.entities import ThreatState


class ThreatStateRepositoryPort(Protocol):
    def get(self, subject_id: str) -> ThreatState | None:
        ...

    def save(self, state: ThreatState) -> None:
        ...

    def expire_before(self, instant: datetime) -> int:
        """Retourne le nombre d'entrees expirees supprimees."""
        ...

    def list_all(self) -> list[ThreatState]:
        """Triees par score decroissant - ListThreatStatesQuery."""
        ...
