"""Contrat de persistance des incidents Active Defense
(plan_active_defense_omega_serv.md, Phase 2).

Revise par rapport a la V1 du port (Phase 0, un seul `save(incident)`
generique) : un `Incident` porte un historique (`observations`/`events`,
des tuples immuables) - un `save()` recevant l'entite COMPLETE a chaque
appel n'a aucun moyen de savoir quelles lignes sont deja persistees et
lesquelles sont nouvelles, ce qui aurait duplique l'historique a chaque
mise a jour. Remplace par des operations d'ajout explicites, jamais
d'upsert sur l'historique - meme categorie de correction que celle deja
faite pour decide_incident_transition (score, pas ThreatLevel)."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentEvent,
    IncidentFilters,
    ThreatObservation,
)


class IncidentRepositoryPort(Protocol):
    def find_open_for(self, subject_id: str) -> Incident | None:
        ...

    def get(self, incident_id: str) -> Incident | None:
        ...

    def create(self, incident_id: str, subject_id: str, opened_at: datetime) -> None:
        ...

    def close(self, incident_id: str, closed_at: datetime) -> None:
        ...

    def add_event(self, incident_id: str, event: IncidentEvent) -> None:
        ...

    def add_observation(self, incident_id: str, observation: ThreatObservation) -> None:
        ...

    def list_recent(self, filters: IncidentFilters) -> list[Incident]:
        ...
