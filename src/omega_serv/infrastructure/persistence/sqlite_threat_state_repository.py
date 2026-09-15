# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implemente ports.threat_state_repository_port.ThreatStateRepositoryPort.
Recoit une connexion DEJA ouverte (sqlite_active_defense_connection.py,
seul module autorise a importer `sqlite3` reellement) - n'a besoin de
`sqlite3` que pour l'annotation de type, sous TYPE_CHECKING, meme
convention que ssl.SSLContext dans asyncio_server.py."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from omega_serv.domain.security.active_defense.entities import ThreatState

if TYPE_CHECKING:
    import sqlite3


def _row_to_state(row: tuple[Any, ...]) -> ThreatState:
    subject_id, score, level, updated_at, expires_at, active_actions = row
    return ThreatState(
        subject_id=subject_id,
        score=score,
        level=level,
        updated_at=datetime.fromisoformat(updated_at),
        expires_at=datetime.fromisoformat(expires_at),
        active_actions=tuple(a for a in active_actions.split(",") if a),
    )


class SqliteThreatStateRepository:
    """Chaque `save()` ecrit aussi une ligne dans
    `active_defense_audit_log` - jamais un effet de bord cache (plan
    §"Principes de conception" : "les actions automatiques sont ecrites
    dans un journal d'audit"), toujours dans la MEME transaction que
    l'etat lui-meme (jamais desynchronisables)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, subject_id: str) -> ThreatState | None:
        row = self._connection.execute(
            "SELECT subject_id, score, level, updated_at, expires_at, active_actions "
            "FROM threat_states WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()
        return None if row is None else _row_to_state(row)

    def save(self, state: ThreatState) -> None:
        self._connection.execute(
            "INSERT INTO threat_states (subject_id, score, level, updated_at, expires_at, active_actions) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(subject_id) DO UPDATE SET "
            "score=excluded.score, level=excluded.level, updated_at=excluded.updated_at, "
            "expires_at=excluded.expires_at, active_actions=excluded.active_actions",
            (
                state.subject_id, state.score, state.level, state.updated_at.isoformat(),
                state.expires_at.isoformat(), ",".join(state.active_actions),
            ),
        )
        self._connection.execute(
            "INSERT INTO active_defense_audit_log (occurred_at, subject_id, kind, detail) VALUES (?, ?, ?, ?)",
            (
                state.updated_at.isoformat(), state.subject_id, "threat_state_saved",
                f"score={state.score} level={state.level}",
            ),
        )
        self._connection.commit()

    def expire_before(self, instant: datetime) -> int:
        cursor = self._connection.execute("DELETE FROM threat_states WHERE expires_at < ?", (instant.isoformat(),))
        self._connection.commit()
        return cursor.rowcount

    def list_all(self) -> list[ThreatState]:
        rows = self._connection.execute(
            "SELECT subject_id, score, level, updated_at, expires_at, active_actions "
            "FROM threat_states ORDER BY score DESC",
        ).fetchall()
        return [_row_to_state(row) for row in rows]
