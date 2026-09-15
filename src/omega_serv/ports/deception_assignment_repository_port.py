# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de persistance des affectations source -> leurre
(plan_active_defense_omega_serv.md, Phase 0). Un `DeceptionProfile`
n'a PAS de repository symetrique : il vient de la configuration
(ActiveDefenseConfig.deception.profiles), jamais d'un etat mutable a
persister - seule l'affectation (qui est actuellement deceptee, et
vers quel profil) est un etat reel."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.security.active_defense.entities import DeceptionAssignment


class DeceptionAssignmentRepositoryPort(Protocol):
    def get(self, subject_id: str) -> DeceptionAssignment | None:
        ...

    def save(self, assignment: DeceptionAssignment) -> None:
        ...

    def release(self, subject_id: str) -> None:
        ...

    def list_active(self) -> list[DeceptionAssignment]:
        ...
