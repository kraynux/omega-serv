"""PurgeExpiredThreatStatesCommand + fermeture automatique des incidents
redevenus silencieux (plan_active_defense_omega_serv.md, Phase 4 :
`decide_incident_closure` policy definie mais jamais appelee ; Phase 6 :
"retention, purge"). Balayage declenche manuellement (CLI `active-defense
purge`), jamais un scheduler en arriere-plan - le score d'une source ne
decroit deja qu'a l'occasion d'une NOUVELLE observation (Phase 1,
`apply_observation`), donc une source devenue silencieuse ne recroise
plus jamais `observe_threat()` : sans ce balayage explicite, son
incident resterait ouvert indefiniment meme apres retour a `normal`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from omega_serv.application.active_defense.manage_incidents import close_incident
from omega_serv.application.active_defense.observe_threat import purge_expired_threat_states
from omega_serv.domain.security.active_defense.config import ActiveDefenseConfig
from omega_serv.domain.security.active_defense.entities import IncidentFilters
from omega_serv.domain.security.active_defense.policies import (
    AUDIT_MAX_ROWS,
    AUDIT_RETENTION_DAYS,
    CLOSED_INCIDENT_RETENTION_DAYS,
    INCIDENT_HISTORY_KEEP_FIRST,
    INCIDENT_HISTORY_KEEP_LAST,
    MAX_CLOSED_INCIDENTS,
    MAX_TRACKED_SUBJECTS,
    decide_incident_closure,
)
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort


@dataclass(frozen=True)
class SweepResult:
    purged_threat_states: int
    closed_incidents: tuple[str, ...]
    purged_closed_incidents: int = 0
    """Incidents fermes depuis plus de 90 j (ou au-dela du plafond) supprimes avec leur historique."""


def close_quiet_incidents(
    threat_state_repository: ThreatStateRepositoryPort,
    incident_repository: IncidentRepositoryPort,
    clock: ClockPort,
    config: ActiveDefenseConfig,
) -> tuple[str, ...]:
    """Ferme les incidents dont la menace est effacee : source revenue a `normal` (ou etat expire) ET
    silencieuse depuis `state_ttl_seconds`. Utilisee par `active-defense purge`, par le bouton « Purger
    maintenant » de l'ecran Incidents ET par l'entretien automatique du serveur (decision utilisateur
    2026-11-01 : un incident dont la menace est effacee quitte la liste tout seul)."""
    now = clock.now()
    closed_ids: list[str] = []
    for incident in incident_repository.list_recent(IncidentFilters(status="open")):
        state = threat_state_repository.get(incident.subject_id)
        level = state.level if state is not None else "normal"
        last_event_at = max(
            (event.occurred_at for event in incident.events), default=incident.opened_at,
        )
        quiet_seconds = (now - last_event_at).total_seconds()
        if decide_incident_closure(level, quiet_seconds, close_after_quiet_seconds=config.state_ttl_seconds):
            close_incident(incident_repository, clock, incident.incident_id)
            closed_ids.append(incident.incident_id)
    return tuple(closed_ids)


def sweep_active_defense(
    threat_state_repository: ThreatStateRepositoryPort,
    incident_repository: IncidentRepositoryPort,
    clock: ClockPort,
    config: ActiveDefenseConfig,
) -> SweepResult:
    """`close_after_quiet_seconds` reutilise `state_ttl_seconds` (deja
    existant, gouverne la pertinence d'un ThreatState) plutot que
    d'ajouter un nouveau champ de config pour un concept tres proche
    (plan §"Mode guerre" ne donne jamais de nom de parametre precis pour
    la duree de silence exigee avant fermeture)."""
    purged = purge_expired_threat_states(threat_state_repository, clock)
    now = clock.now()
    threat_state_repository.cap_tracked_subjects(MAX_TRACKED_SUBJECTS)
    threat_state_repository.prune_audit_log(now - timedelta(days=AUDIT_RETENTION_DAYS), AUDIT_MAX_ROWS)
    incident_repository.prune_history(INCIDENT_HISTORY_KEEP_FIRST, INCIDENT_HISTORY_KEEP_LAST)
    closed_ids = close_quiet_incidents(threat_state_repository, incident_repository, clock, config)
    purged_closed = incident_repository.purge_closed(
        now - timedelta(days=CLOSED_INCIDENT_RETENTION_DAYS), MAX_CLOSED_INCIDENTS,
    )
    return SweepResult(
        purged_threat_states=purged, closed_incidents=closed_ids, purged_closed_incidents=purged_closed,
    )
