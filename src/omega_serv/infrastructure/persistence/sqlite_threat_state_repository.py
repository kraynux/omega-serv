"""Implemente ports.threat_state_repository_port.ThreatStateRepositoryPort.
Recoit une connexion DEJA ouverte (sqlite_active_defense_connection.py,
seul module autorise a importer `sqlite3` reellement) - n'a besoin de
`sqlite3` que pour l'annotation de type, sous TYPE_CHECKING, meme
convention que ssl.SSLContext dans asyncio_server.py."""
from __future__ import annotations

from collections.abc import Sequence
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
        self.save_many((state,))

    def save_many(self, states: Sequence[ThreatState]) -> None:
        """`executemany` : la boucle sur les lignes se fait dans SQLite (C), pas en Python -
        l'ecriture differee d'Active Defense partage le GIL avec la boucle qui sert les visiteurs
        (mesure du 2026-10-26)."""
        if not states:
            return
        self._connection.executemany(
            "INSERT INTO threat_states (subject_id, score, level, updated_at, expires_at, active_actions) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(subject_id) DO UPDATE SET "
            "score=excluded.score, level=excluded.level, updated_at=excluded.updated_at, "
            "expires_at=excluded.expires_at, active_actions=excluded.active_actions",
            [
                (s.subject_id, s.score, s.level, s.updated_at.isoformat(), s.expires_at.isoformat(), ",".join(s.active_actions))
                for s in states
            ],
        )
        self._connection.executemany(
            "INSERT INTO active_defense_audit_log (occurred_at, subject_id, kind, detail) VALUES (?, ?, ?, ?)",
            [
                (s.updated_at.isoformat(), s.subject_id, "threat_state_saved", f"score={s.score} level={s.level}")
                for s in states
            ],
        )
        self._connection.commit()

    def prune_audit_log(self, older_than: datetime, max_rows: int) -> int:
        """Decision utilisateur 2026-10-26 : le journal d'audit n'etait jamais purge, un attaquant
        changeant d'adresse a chaque requete pouvait remplir le disque (une ligne par ecriture
        d'etat). Duree ET plafond : la duree garde un historique utile, le plafond ferme le trou
        meme sous une attaque massive (on garde toujours les lignes les plus recentes)."""
        removed = self._connection.execute(
            "DELETE FROM active_defense_audit_log WHERE occurred_at < ?", (older_than.isoformat(),),
        ).rowcount
        removed += self._connection.execute(
            "DELETE FROM active_defense_audit_log WHERE id <= "
            "(SELECT id FROM active_defense_audit_log ORDER BY id DESC LIMIT 1 OFFSET ?)",
            (max_rows,),
        ).rowcount
        self._connection.commit()
        return removed

    def cap_tracked_subjects(self, max_subjects: int) -> int:
        """Plafond des sources suivies (MAX_TRACKED_SUBJECTS) : sources « normal » les plus
        anciennes d'abord, puis, seulement s'il n'en reste plus, les plus anciennes tous niveaux."""
        (count,) = self._connection.execute("SELECT COUNT(*) FROM threat_states").fetchone()
        excess = count - max_subjects
        if excess <= 0:
            return 0
        removed = self._connection.execute(
            "DELETE FROM threat_states WHERE subject_id IN "
            "(SELECT subject_id FROM threat_states WHERE level = 'normal' ORDER BY updated_at LIMIT ?)",
            (excess,),
        ).rowcount
        if removed < excess:
            removed += self._connection.execute(
                "DELETE FROM threat_states WHERE subject_id IN "
                "(SELECT subject_id FROM threat_states ORDER BY updated_at LIMIT ?)",
                (excess - removed,),
            ).rowcount
        self._connection.commit()
        return removed

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
