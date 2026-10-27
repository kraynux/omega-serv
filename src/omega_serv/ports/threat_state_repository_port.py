"""Contrat de persistance de l'etat de menace par source
(plan_active_defense_omega_serv.md, Phase 0). `instance_id` absent des
signatures - chaque process OMEGA-SERV a sa propre base locale, le
cloisonnement par instance est deja garanti par des fichiers separes
(voir "Ports applicatifs" du plan)."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from omega_serv.domain.security.active_defense.entities import ThreatState


class ThreatStateRepositoryPort(Protocol):
    def get(self, subject_id: str) -> ThreatState | None:
        ...

    def save(self, state: ThreatState) -> None:
        ...

    def save_many(self, states: Sequence[ThreatState]) -> None:
        """Comme `save()` pour chaque etat, dans l'ordre (le dernier d'un meme sujet gagne), en
        une seule passe : l'ecriture differee groupe ainsi les etats d'un lot."""
        ...

    def prune_audit_log(self, older_than: datetime, max_rows: int) -> int:
        """Supprime les lignes d'audit anterieures a `older_than`, puis les plus anciennes au-dela
        de `max_rows`. Retourne le nombre de lignes supprimees."""
        ...

    def cap_tracked_subjects(self, max_subjects: int) -> int:
        """Au-dela de `max_subjects`, supprime les sources « normal » les plus anciennes d'abord."""
        ...

    def expire_before(self, instant: datetime) -> int:
        """Retourne le nombre d'entrees expirees supprimees."""
        ...

    def list_all(self) -> list[ThreatState]:
        """Triees par score decroissant - ListThreatStatesQuery."""
        ...
