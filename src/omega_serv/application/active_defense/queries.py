"""Queries en lecture seule Active Defense (plan_active_defense_omega_
serv.md, Phase 1/2) - meme regroupement qu'application/security/ (peu de
fichiers, pas un fichier par query)."""
from __future__ import annotations

from collections.abc import Callable

from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentEvent,
    IncidentFilters,
    Indicator,
    ThreatState,
)
from omega_serv.domain.security.active_defense.policies import extract_indicators
from omega_serv.domain.security.active_defense.value_objects import ThreatLevel
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort


def list_threat_states(repository: ThreatStateRepositoryPort, *, level: ThreatLevel | None = None) -> list[ThreatState]:
    """ListThreatStatesQuery - triees par score decroissant (deja fait
    par le repository), filtrable par niveau (`omega-serv threats list
    --level hostile`)."""
    states = repository.list_all()
    return states if level is None else [s for s in states if s.level == level]


def get_threat_state(repository: ThreatStateRepositoryPort, subject_id: str) -> ThreatState | None:
    """GetThreatStateQuery."""
    return repository.get(subject_id)


def list_incidents(repository: IncidentRepositoryPort, filters: IncidentFilters) -> list[Incident]:
    """ListIncidentsQuery."""
    return repository.list_recent(filters)


def get_incident_timeline(repository: IncidentRepositoryPort, incident_id: str) -> tuple[IncidentEvent, ...]:
    """GetIncidentTimelineQuery - deja triee chronologiquement par le
    repository (voir SqliteIncidentRepository::_load_events)."""
    incident = repository.get(incident_id)
    return () if incident is None else incident.events


def get_incident_iocs(
    repository: IncidentRepositoryPort, incident_id: str, id_factory: Callable[[], str],
) -> list[Indicator]:
    """GetIncidentIoCsQuery - `id_factory` est injecte par l'appelant
    (meme raison que extract_indicators lui-meme : generer un UUID est
    impur, jamais fait dans le domaine)."""
    incident = repository.get(incident_id)
    return [] if incident is None else extract_indicators(incident, id_factory)
