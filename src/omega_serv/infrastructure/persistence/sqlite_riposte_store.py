"""Implemente ports.riposte_store_port.RiposteStorePort sur une connexion deja ouverte
(sqlite_riposte_connection.py). `sqlite3` seulement pour l'annotation de type, sous TYPE_CHECKING
(meme convention que sqlite_threat_state_repository.py). Chaque ecriture est une transaction courte :
jamais un verrou tenu pendant une autre operation (plan §3.6)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from omega_serv.domain.security.riposte.actions import (
    FINISHED_STATES,
    IN_PROGRESS_STATES,
    Exemption,
    RiposteAction,
    RiposteCommand,
)
from omega_serv.domain.security.riposte.decide import Decision, Reason
from omega_serv.domain.security.riposte.history import SourceHistory
from omega_serv.ports.riposte_store_port import FollowerPosition

if TYPE_CHECKING:
    import sqlite3


class SqliteRiposteStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def close(self) -> None:
        self._connection.close()

    def get_position(self, journal: str) -> FollowerPosition | None:
        row = self._connection.execute(
            "SELECT inode, device, offset, fingerprint, fingerprint_length FROM follower_positions WHERE journal = ?",
            (journal,),
        ).fetchone()
        if row is None:
            return None
        inode, device, offset, fingerprint, fingerprint_length = row
        return FollowerPosition(
            inode=inode, device=device, offset=offset, fingerprint=fingerprint, fingerprint_length=fingerprint_length,
        )

    def save_position(self, journal: str, position: FollowerPosition) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO follower_positions (journal, inode, device, offset, fingerprint, fingerprint_length) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(journal) DO UPDATE SET inode=excluded.inode, "
                "device=excluded.device, offset=excluded.offset, fingerprint=excluded.fingerprint, "
                "fingerprint_length=excluded.fingerprint_length",
                (journal, position.inode, position.device, position.offset, position.fingerprint,
                 position.fingerprint_length),
            )

    def mark_seen(self, event_id: str, seen_at: datetime) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO seen_events (event_id, seen_at) VALUES (?, ?)", (event_id, seen_at.isoformat()),
            )
        return cursor.rowcount == 1

    def purge_seen_before(self, cutoff: datetime) -> int:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM seen_events WHERE seen_at < ?", (cutoff.isoformat(),))
        return cursor.rowcount

    def get_state(self, key: str) -> str | None:
        row = self._connection.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def set_state(self, key: str, value: str) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def append_audit(self, occurred_at: datetime, kind: str, detail: str) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO audit (occurred_at, kind, detail) VALUES (?, ?, ?)", (occurred_at.isoformat(), kind, detail),
            )

    def purge_audit(self, before: datetime, max_rows: int) -> int:
        with self._connection:
            by_age = self._connection.execute("DELETE FROM audit WHERE occurred_at < ?", (before.isoformat(),)).rowcount
            by_count = self._connection.execute(
                "DELETE FROM audit WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT ?)", (max_rows,),
            ).rowcount
        return by_age + by_count

    # --- Lot 3 : historique des sources et decisions -------------------------------------------

    def get_source(self, ip: str) -> SourceHistory | None:
        row = self._connection.execute("SELECT history FROM sources WHERE ip = ?", (ip,)).fetchone()
        if row is None:
            return None
        try:
            return SourceHistory.from_dict(json.loads(row[0]))
        except (ValueError, KeyError, TypeError):
            return None  # ligne illisible : la source repart d'une memoire vide, jamais une exception

    def save_source(self, history: SourceHistory, updated_at: datetime) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO sources (ip, history, updated_at) VALUES (?, ?, ?) ON CONFLICT(ip) DO UPDATE SET "
                "history=excluded.history, updated_at=excluded.updated_at",
                (history.ip, json.dumps(history.to_dict(), sort_keys=True), updated_at.isoformat()),
            )

    def list_sources(self, limit: int) -> list[tuple[SourceHistory, datetime]]:
        rows = self._connection.execute(
            "SELECT history, updated_at FROM sources ORDER BY updated_at DESC LIMIT ?", (limit,),
        ).fetchall()
        result = []
        for history, updated_at in rows:
            try:
                result.append((SourceHistory.from_dict(json.loads(history)), datetime.fromisoformat(updated_at)))
            except (ValueError, KeyError, TypeError):
                continue
        return result

    def purge_sources(self, before: datetime, max_rows: int) -> int:
        with self._connection:
            by_age = self._connection.execute("DELETE FROM sources WHERE updated_at < ?", (before.isoformat(),)).rowcount
            by_count = self._connection.execute(
                "DELETE FROM sources WHERE ip NOT IN (SELECT ip FROM sources ORDER BY updated_at DESC LIMIT ?)",
                (max_rows,),
            ).rowcount
        return by_age + by_count

    def append_decision(self, decision: Decision, applied: bool) -> None:
        reasons = json.dumps([[r.code, dict(r.params)] for r in decision.reasons], sort_keys=True)
        with self._connection:
            self._connection.execute(
                "INSERT INTO decisions (decided_at, ip, event_id, status, policy_id, action, tier_index, "
                "duration_seconds, decoy_profile, reasons, applied) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (decision.decided_at.isoformat(), decision.ip, decision.event_id, decision.status, decision.policy_id,
                 decision.action, decision.tier_index, decision.duration_seconds, decision.decoy_profile, reasons,
                 1 if applied else 0),
            )

    def list_decisions(self, limit: int, ip: str | None = None) -> list[tuple[Decision, bool]]:
        if ip is None:
            rows = self._connection.execute(
                "SELECT decided_at, ip, event_id, status, policy_id, action, tier_index, duration_seconds, "
                "decoy_profile, reasons, applied FROM decisions ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT decided_at, ip, event_id, status, policy_id, action, tier_index, duration_seconds, "
                "decoy_profile, reasons, applied FROM decisions WHERE ip = ? ORDER BY id DESC LIMIT ?", (ip, limit),
            ).fetchall()
        decisions = []
        for decided_at, row_ip, event_id, status, policy_id, action, tier, duration, profile, reasons, applied in rows:
            decisions.append((Decision(
                status=status, ip=row_ip, event_id=event_id, decided_at=datetime.fromisoformat(decided_at),
                policy_id=policy_id, action=action, tier_index=tier, duration_seconds=duration, decoy_profile=profile,
                reasons=tuple(Reason(code, tuple(sorted(params_.items()))) for code, params_ in json.loads(reasons)),
            ), bool(applied)))
        return decisions

    def purge_decisions(self, before: datetime, max_rows: int) -> int:
        with self._connection:
            by_age = self._connection.execute(
                "DELETE FROM decisions WHERE decided_at < ?", (before.isoformat(),)).rowcount
            by_count = self._connection.execute(
                "DELETE FROM decisions WHERE id NOT IN (SELECT id FROM decisions ORDER BY id DESC LIMIT ?)", (max_rows,),
            ).rowcount
        return by_age + by_count

    # --- Lot 4 : registre des actions, exemptions, commandes -----------------------------------

    def save_action(self, action: RiposteAction) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO actions (id, ip, kind, policy_id, created_at, ends_at, state, tier_index, decoy_profile, "
                "subject_ids, detail, finished_at, finished_by, counts_for_recidive, event_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "ends_at=excluded.ends_at, state=excluded.state, subject_ids=excluded.subject_ids, "
                "detail=excluded.detail, finished_at=excluded.finished_at, finished_by=excluded.finished_by, "
                "counts_for_recidive=excluded.counts_for_recidive",
                (action.id, action.ip, action.kind, action.policy_id, action.created_at.isoformat(),
                 action.ends_at.isoformat(), action.state, action.tier_index, action.decoy_profile,
                 json.dumps(list(action.subject_ids)), action.detail,
                 action.finished_at.isoformat() if action.finished_at else None, action.finished_by,
                 1 if action.counts_for_recidive else 0, action.event_id),
            )

    @staticmethod
    def _action(row: tuple[object, ...]) -> RiposteAction:
        (action_id, ip, kind, policy_id, created_at, ends_at, state, tier_index, decoy_profile, subject_ids, detail,
         finished_at, finished_by, counts, event_id) = row
        return RiposteAction(
            id=str(action_id), ip=str(ip), kind=str(kind), policy_id=str(policy_id),
            created_at=datetime.fromisoformat(str(created_at)), ends_at=datetime.fromisoformat(str(ends_at)),
            state=state,  # type: ignore[arg-type]
            tier_index=tier_index if isinstance(tier_index, int) else None,
            decoy_profile=decoy_profile if isinstance(decoy_profile, str) else None,
            subject_ids=tuple(json.loads(str(subject_ids))), detail=str(detail),
            finished_at=datetime.fromisoformat(finished_at) if isinstance(finished_at, str) else None,
            finished_by=finished_by,  # type: ignore[arg-type]
            counts_for_recidive=bool(counts), event_id=str(event_id),
        )

    def get_action(self, action_id: str) -> RiposteAction | None:
        row = self._connection.execute(
            "SELECT id, ip, kind, policy_id, created_at, ends_at, state, tier_index, decoy_profile, subject_ids, "
            "detail, finished_at, finished_by, counts_for_recidive, event_id FROM actions WHERE id = ?", (action_id,),
        ).fetchone()
        return None if row is None else self._action(row)

    def list_actions(self, *, in_progress: bool, limit: int, ip: str | None = None,
                     policy_id: str | None = None) -> list[RiposteAction]:
        # Requete fixe (filtres a NULL = ignores) : jamais de SQL assemble morceau par morceau.
        states = sorted(IN_PROGRESS_STATES if in_progress else FINISHED_STATES)
        rows = self._connection.execute(
            "SELECT id, ip, kind, policy_id, created_at, ends_at, state, tier_index, decoy_profile, subject_ids, "
            "detail, finished_at, finished_by, counts_for_recidive, event_id FROM actions "
            "WHERE state IN (?, ?, ?) AND (? IS NULL OR ip = ?) AND (? IS NULL OR policy_id = ?) "
            "ORDER BY created_at DESC LIMIT ?",
            (*states, ip, ip, policy_id, policy_id, limit),
        ).fetchall()
        return [self._action(row) for row in rows]

    def count_in_progress(self, *, bans_only: bool, ip: str | None = None) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM actions WHERE state IN ('pending', 'applied', 'unknown') "
            "AND (? = 0 OR kind IN ('local_ban', 'local_and_network_ban')) AND (? IS NULL OR ip = ?)",
            (1 if bans_only else 0, ip, ip),
        ).fetchone()
        return int(row[0])

    def purge_finished_actions(self, before: datetime, max_rows: int) -> int:
        with self._connection:
            by_age = self._connection.execute(
                "DELETE FROM actions WHERE state IN ('failed', 'expired', 'revoked') AND created_at < ?",
                (before.isoformat(),),
            ).rowcount
            by_count = self._connection.execute(
                "DELETE FROM actions WHERE state IN ('failed', 'expired', 'revoked') AND id NOT IN "
                "(SELECT id FROM actions WHERE state IN ('failed', 'expired', 'revoked') "
                "ORDER BY created_at DESC LIMIT ?)", (max_rows,),
            ).rowcount
        return by_age + by_count

    def add_exemption(self, exemption: Exemption) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO exemptions (network, created_at, until, origin_action_id) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(network) DO UPDATE SET created_at=excluded.created_at, until=excluded.until, "
                "origin_action_id=excluded.origin_action_id",
                (exemption.network, exemption.created_at.isoformat(),
                 exemption.until.isoformat() if exemption.until else None, exemption.origin_action_id),
            )

    def list_exemptions(self) -> list[Exemption]:
        rows = self._connection.execute(
            "SELECT network, created_at, until, origin_action_id FROM exemptions ORDER BY created_at DESC",
        ).fetchall()
        return [Exemption(network=network, created_at=datetime.fromisoformat(created_at),
                          until=datetime.fromisoformat(until) if until else None, origin_action_id=origin)
                for network, created_at, until, origin in rows]

    def remove_exemption(self, network: str) -> bool:
        with self._connection:
            return self._connection.execute("DELETE FROM exemptions WHERE network = ?", (network,)).rowcount > 0

    def purge_exemptions(self, now: datetime) -> int:
        with self._connection:
            return self._connection.execute(
                "DELETE FROM exemptions WHERE until IS NOT NULL AND until <= ?", (now.isoformat(),),
            ).rowcount

    def add_command(self, kind: str, params: dict[str, object], created_at: datetime) -> int:
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO commands (kind, params, created_at) VALUES (?, ?, ?)",
                (kind, json.dumps(params, sort_keys=True), created_at.isoformat()),
            )
        return int(cursor.lastrowid or 0)

    @staticmethod
    def _command(row: tuple[object, ...]) -> RiposteCommand:
        command_id, kind, params, created_at, state, result, result_params, done_at = row
        return RiposteCommand(
            id=int(command_id), kind=str(kind), params=json.loads(str(params)),  # type: ignore[call-overload]
            created_at=datetime.fromisoformat(str(created_at)), state=state,  # type: ignore[arg-type]
            result=str(result), result_params=json.loads(str(result_params)),
            done_at=datetime.fromisoformat(done_at) if isinstance(done_at, str) else None,
        )

    def pending_commands(self, limit: int) -> list[RiposteCommand]:
        rows = self._connection.execute(
            "SELECT id, kind, params, created_at, state, result, result_params, done_at FROM commands "
            "WHERE state = 'pending' ORDER BY id LIMIT ?", (limit,),
        ).fetchall()
        return [self._command(row) for row in rows]

    def get_command(self, command_id: int) -> RiposteCommand | None:
        row = self._connection.execute(
            "SELECT id, kind, params, created_at, state, result, result_params, done_at FROM commands WHERE id = ?",
            (command_id,),
        ).fetchone()
        return None if row is None else self._command(row)

    def finish_command(self, command_id: int, *, state: str, result: str, result_params: dict[str, object],
                       done_at: datetime) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE commands SET state = ?, result = ?, result_params = ?, done_at = ? WHERE id = ?",
                (state, result, json.dumps(result_params, sort_keys=True), done_at.isoformat(), command_id),
            )

    def purge_commands(self, before: datetime, max_rows: int) -> int:
        with self._connection:
            by_age = self._connection.execute(
                "DELETE FROM commands WHERE state != 'pending' AND created_at < ?", (before.isoformat(),),
            ).rowcount
            by_count = self._connection.execute(
                "DELETE FROM commands WHERE id NOT IN (SELECT id FROM commands ORDER BY id DESC LIMIT ?)", (max_rows,),
            ).rowcount
        return by_age + by_count

    def forget_source(self, ip: str) -> bool:
        with self._connection:
            return self._connection.execute("DELETE FROM sources WHERE ip = ?", (ip,)).rowcount > 0
