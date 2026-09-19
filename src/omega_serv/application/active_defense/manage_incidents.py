"""Cas d'usage CreateOrUpdateIncidentCommand/CloseIncidentCommand
(plan_active_defense_omega_serv.md, Phase 2)."""
from __future__ import annotations

import uuid

from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentEvent,
    ThreatObservation,
)
from omega_serv.domain.security.active_defense.events import IncidentOpened
from omega_serv.domain.security.active_defense.policies import decide_incident_transition
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort


def create_or_update_incident(
    incident_repository: IncidentRepositoryPort,
    clock: ClockPort,
    *,
    subject_id: str,
    observation: ThreatObservation,
    score: int,
    incident_score_threshold: int,
) -> tuple[Incident | None, IncidentOpened | None]:
    """Retourne (None, None) si le score reste sous le seuil - jamais
    d'incident cree/mis a jour pour une menace encore "suspicious"
    (plan §"Domaine metier" : les observations detaillees ne sont
    persistees qu'a partir du moment ou une enquete est justifiee)."""
    existing = incident_repository.find_open_for(subject_id)
    transition = decide_incident_transition(existing, score, incident_score_threshold=incident_score_threshold)
    if transition == "no_change":
        return None, None

    now = clock.now()
    opened_event: IncidentOpened | None = None
    if transition == "open_new":
        incident_id = str(uuid.uuid4())
        incident_repository.create(incident_id, subject_id, now)
        opened_event = IncidentOpened(incident_id=incident_id, subject_id=subject_id, occurred_at=now)
    else:
        assert existing is not None
        incident_id = existing.incident_id

    incident_repository.add_observation(incident_id, observation)
    incident_repository.add_event(
        incident_id, IncidentEvent(occurred_at=now, kind=observation.kind, detail=observation.detail),
    )

    incident = incident_repository.get(incident_id)
    assert incident is not None
    return incident, opened_event


def close_incident(incident_repository: IncidentRepositoryPort, clock: ClockPort, incident_id: str) -> Incident | None:
    """CloseIncidentCommand - retourne None si l'incident est introuvable
    ou deja ferme (jamais une erreur : fermer deux fois de suite doit
    rester sans effet, pas un echec)."""
    incident = incident_repository.get(incident_id)
    if incident is None or incident.status == "closed":
        return None
    incident_repository.close(incident_id, clock.now())
    return incident_repository.get(incident_id)
