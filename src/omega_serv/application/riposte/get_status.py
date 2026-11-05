"""Etat du processus RIPOSTE pour `riposte status` et l'ecran Etat (lot 2) - lecture seule de la base."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from omega_serv.application.riposte.run_riposte import (
    STATE_EMERGENCY_STOP,
    STATE_HEARTBEAT,
    STATE_PID,
    STATE_STARTED,
    STATE_STATS,
)
from omega_serv.ports.riposte_store_port import RiposteStorePort

ALIVE_WITHIN_SECONDS = 15.0
"""Battement plus ancien que ca (3 battements manques) : processus considere arrete."""


@dataclass(frozen=True)
class RiposteStatus:
    running: bool
    pid: int | None
    started_at: datetime | None
    heartbeat_at: datetime | None
    emergency_stop: bool
    lines_read: int = 0
    new_events: int = 0
    duplicates: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    historical: int = 0
    decisions: dict[str, int] = field(default_factory=dict)
    """Decisions depuis le demarrage, par statut (matched, rejected_by_safety, stopped, observed)."""
    last_event_at: dict[str, datetime] = field(default_factory=dict)


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_riposte_status(store: RiposteStorePort, now: datetime) -> RiposteStatus:
    heartbeat = _parse_time(store.get_state(STATE_HEARTBEAT))
    pid_text = store.get_state(STATE_PID)
    stats: dict = {}
    raw_stats = store.get_state(STATE_STATS)
    if raw_stats:
        try:
            stats = json.loads(raw_stats)
        except ValueError:
            stats = {}
    last_event_at = {
        name: parsed for name, value in stats.get("last_event_at", {}).items()
        if (parsed := _parse_time(value)) is not None
    }
    return RiposteStatus(
        running=heartbeat is not None and (now - heartbeat).total_seconds() <= ALIVE_WITHIN_SECONDS,
        pid=int(pid_text) if pid_text and pid_text.isdigit() else None,
        started_at=_parse_time(store.get_state(STATE_STARTED)),
        heartbeat_at=heartbeat,
        emergency_stop=store.get_state(STATE_EMERGENCY_STOP) == "1",
        lines_read=int(stats.get("lines_read", 0)),
        new_events=int(stats.get("new_events", 0)),
        duplicates=int(stats.get("duplicates", 0)),
        rejected={str(k): int(v) for k, v in stats.get("rejected", {}).items()},
        historical=int(stats.get("historical", 0)),
        decisions={str(k): int(v) for k, v in stats.get("decisions", {}).items()},
        last_event_at=last_event_at,
    )
