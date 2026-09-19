"""Implemente ports.deception_assignment_repository_port.
DeceptionAssignmentRepositoryPort. Meme convention que les autres
repositories sqlite_*.py : connexion deja ouverte, `sqlite3` sous
TYPE_CHECKING seulement."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from omega_serv.domain.security.active_defense.entities import DeceptionAssignment

if TYPE_CHECKING:
    import sqlite3


class SqliteDeceptionAssignmentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, subject_id: str) -> DeceptionAssignment | None:
        row = self._connection.execute(
            "SELECT subject_id, profile_name, assigned_at, expires_at FROM deception_assignments "
            "WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()
        if row is None:
            return None
        subject_id, profile_name, assigned_at, expires_at = row
        return DeceptionAssignment(
            subject_id=subject_id, profile_name=profile_name,
            assigned_at=datetime.fromisoformat(assigned_at), expires_at=datetime.fromisoformat(expires_at),
        )

    def save(self, assignment: DeceptionAssignment) -> None:
        self._connection.execute(
            "INSERT INTO deception_assignments (subject_id, profile_name, assigned_at, expires_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(subject_id) DO UPDATE SET "
            "profile_name=excluded.profile_name, assigned_at=excluded.assigned_at, expires_at=excluded.expires_at",
            (
                assignment.subject_id, assignment.profile_name, assignment.assigned_at.isoformat(),
                assignment.expires_at.isoformat(),
            ),
        )
        self._connection.commit()

    def release(self, subject_id: str) -> None:
        self._connection.execute("DELETE FROM deception_assignments WHERE subject_id = ?", (subject_id,))
        self._connection.commit()

    def list_active(self) -> list[DeceptionAssignment]:
        """Retourne toutes les affectations encore enregistrees (jamais
        liberees), EXPIREES ou non - la distinction "encore valide comme
        decision de routage" reste une decision de domaine
        (is_assignment_active), jamais dupliquee ici en SQL sans horloge
        injectee. L'appelant (CLI `deception list`) filtre lui-meme si
        besoin d'une vue strictement "toujours active"."""
        rows = self._connection.execute(
            "SELECT subject_id, profile_name, assigned_at, expires_at FROM deception_assignments "
            "ORDER BY assigned_at DESC",
        ).fetchall()
        return [
            DeceptionAssignment(
                subject_id=r[0], profile_name=r[1],
                assigned_at=datetime.fromisoformat(r[2]), expires_at=datetime.fromisoformat(r[3]),
            )
            for r in rows
        ]
