# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implemente ports.incident_repository_port.IncidentRepositoryPort.
Meme convention que SqliteThreatStateRepository : recoit une connexion
deja ouverte, n'importe `sqlite3` que sous TYPE_CHECKING. Historique
(observations/events) en tables enfants append-only - jamais un
`save()` generique qui re-inserait tout l'historique a chaque appel
(voir le docstring du port pour le pourquoi)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from omega_serv.domain.security.active_defense.entities import (
    Incident,
    IncidentEvent,
    IncidentFilters,
    ThreatObservation,
)

if TYPE_CHECKING:
    import sqlite3


def _load_events(connection: sqlite3.Connection, incident_id: str) -> tuple[IncidentEvent, ...]:
    rows = connection.execute(
        "SELECT occurred_at, kind, detail FROM incident_events WHERE incident_id = ? ORDER BY occurred_at",
        (incident_id,),
    ).fetchall()
    return tuple(IncidentEvent(occurred_at=datetime.fromisoformat(r[0]), kind=r[1], detail=r[2]) for r in rows)


def _load_observations(connection: sqlite3.Connection, incident_id: str) -> tuple[ThreatObservation, ...]:
    rows = connection.execute(
        "SELECT subject_id, observed_at, kind, attack_class, score_delta, detail "
        "FROM incident_observations WHERE incident_id = ? ORDER BY observed_at",
        (incident_id,),
    ).fetchall()
    return tuple(
        ThreatObservation(
            subject_id=r[0], observed_at=datetime.fromisoformat(r[1]), kind=r[2], attack_class=r[3],
            score_delta=r[4], detail=r[5],
        )
        for r in rows
    )


def _row_to_incident(connection: sqlite3.Connection, row: tuple[Any, ...]) -> Incident:
    incident_id, subject_id, status, opened_at, closed_at = row
    return Incident(
        incident_id=incident_id,
        subject_id=subject_id,
        status=status,
        opened_at=datetime.fromisoformat(opened_at),
        closed_at=datetime.fromisoformat(closed_at) if closed_at else None,
        observations=_load_observations(connection, incident_id),
        events=_load_events(connection, incident_id),
    )


class SqliteIncidentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def find_open_for(self, subject_id: str) -> Incident | None:
        row = self._connection.execute(
            "SELECT incident_id, subject_id, status, opened_at, closed_at FROM incidents "
            "WHERE subject_id = ? AND status = 'open' LIMIT 1",
            (subject_id,),
        ).fetchone()
        return None if row is None else _row_to_incident(self._connection, row)

    def get(self, incident_id: str) -> Incident | None:
        row = self._connection.execute(
            "SELECT incident_id, subject_id, status, opened_at, closed_at FROM incidents WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        return None if row is None else _row_to_incident(self._connection, row)

    def create(self, incident_id: str, subject_id: str, opened_at: datetime) -> None:
        self._connection.execute(
            "INSERT INTO incidents (incident_id, subject_id, status, opened_at, closed_at) "
            "VALUES (?, ?, 'open', ?, NULL)",
            (incident_id, subject_id, opened_at.isoformat()),
        )
        self._connection.commit()

    def close(self, incident_id: str, closed_at: datetime) -> None:
        self._connection.execute(
            "UPDATE incidents SET status = 'closed', closed_at = ? WHERE incident_id = ?",
            (closed_at.isoformat(), incident_id),
        )
        self._connection.commit()

    def add_event(self, incident_id: str, event: IncidentEvent) -> None:
        self._connection.execute(
            "INSERT INTO incident_events (incident_id, occurred_at, kind, detail) VALUES (?, ?, ?, ?)",
            (incident_id, event.occurred_at.isoformat(), event.kind, event.detail),
        )
        self._connection.commit()

    def add_observation(self, incident_id: str, observation: ThreatObservation) -> None:
        self._connection.execute(
            "INSERT INTO incident_observations "
            "(incident_id, subject_id, observed_at, kind, attack_class, score_delta, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                incident_id, observation.subject_id, observation.observed_at.isoformat(), observation.kind,
                observation.attack_class, observation.score_delta, observation.detail,
            ),
        )
        self._connection.commit()

    def list_recent(self, filters: IncidentFilters) -> list[Incident]:
        clauses: list[str] = []
        params: list[Any] = []
        if filters.status is not None:
            clauses.append("status = ?")
            params.append(filters.status)
        if filters.since is not None:
            clauses.append("opened_at >= ?")
            params.append(filters.since.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            f"SELECT incident_id, subject_id, status, opened_at, closed_at FROM incidents "
            f"{where} ORDER BY opened_at DESC",
            params,
        ).fetchall()
        return [_row_to_incident(self._connection, row) for row in rows]
