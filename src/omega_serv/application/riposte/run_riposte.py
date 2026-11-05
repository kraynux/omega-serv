"""Boucle du processus RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.1-3.2, lot 2).

Lot 2 : suivre les journaux et tenir les compteurs a jour, sans decider ni agir. Les decisions
(lot 3) et les actions (lot 4) se brancheront sur `on_events`.

Ecrit dans l'etat (lu par `riposte status` et l'ecran Etat) : `heartbeat_at` toutes les
`heartbeat_seconds` au plus (jamais une ecriture par tour), compteurs en JSON. Une erreur de base ou
de journal n'arrete jamais la boucle : elle est comptee, signalee une fois par serie, et le tour
suivant reessaie - le serveur web, lui, n'en depend jamais."""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from omega_serv.application.riposte.follow_journals import FollowStats, JournalSource, follow_once
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.riposte_store_port import RiposteStorePort

STATE_HEARTBEAT = "heartbeat_at"
STATE_STARTED = "started_at"
STATE_PID = "pid"
STATE_STATS = "stats"
STATE_EMERGENCY_STOP = "emergency_stop"

SEEN_EVENTS_RETENTION = timedelta(days=2)
"""Un journal relu apres reecriture ne remonte jamais plus loin que quelques heures : 2 jours de
dedoublonnage suffisent, et la table reste petite meme sous botnet."""
STARTUP_MARGIN = timedelta(seconds=60)
"""Evenements jusqu'a 60 s avant le demarrage de RIPOSTE : traites (demarrage, relance apres panne) ;
plus anciens : historique, ecartes."""
AUDIT_RETENTION = timedelta(days=90)
AUDIT_MAX_ROWS = 100_000


def stats_to_json(stats: FollowStats, extra: dict[str, object] | None = None) -> str:
    return json.dumps({
        **(extra or {}),
        "lines_read": stats.lines_read,
        "new_events": stats.new_events,
        "duplicates": stats.duplicates,
        "historical": stats.historical,
        "rejected": dict(stats.rejected),
        "last_event_at": {name: value.isoformat() for name, value in stats.last_event_at.items()},
    }, sort_keys=True)


def run_riposte(
    sources: Sequence[JournalSource],
    store: RiposteStorePort,
    clock: ClockPort,
    *,
    should_stop: Callable[[], bool],
    sleep: Callable[[float], None],
    report_error: Callable[[str], None],
    on_events: Callable[[list[ObservedEvent]], object] | None = None,
    on_tick: Callable[[], None] | None = None,
    maintenance: Callable[[datetime], None] | None = None,
    extra_stats: Callable[[], dict[str, object]] | None = None,
    poll_seconds: float = 1.0,
    heartbeat_seconds: float = 5.0,
    pid: int | None = None,
) -> FollowStats:
    stats = FollowStats()
    started = clock.now()
    store.set_state(STATE_STARTED, started.isoformat())
    if pid is not None:
        store.set_state(STATE_PID, str(pid))
    last_heartbeat: datetime | None = None
    last_maintenance = started
    failing_since: str | None = None
    def current_stats() -> str:
        return stats_to_json(stats, extra_stats() if extra_stats is not None else None)

    while not should_stop():
        try:
            if on_tick is not None:
                on_tick()  # ex. rechargement demande par SIGHUP, fait ici et jamais dans le gestionnaire de signal
            events = follow_once(sources, store, clock, stats, not_before=started - STARTUP_MARGIN)
            if events and on_events is not None:
                on_events(events)
            now = clock.now()
            if last_heartbeat is None or (now - last_heartbeat).total_seconds() >= heartbeat_seconds:
                store.set_state(STATE_HEARTBEAT, now.isoformat())
                store.set_state(STATE_STATS, current_stats())
                last_heartbeat = now
            if now - last_maintenance >= timedelta(hours=1):
                store.purge_seen_before(now - SEEN_EVENTS_RETENTION)
                store.purge_audit(now - AUDIT_RETENTION, AUDIT_MAX_ROWS)
                if maintenance is not None:
                    maintenance(now)
                last_maintenance = now
            if failing_since is not None:
                report_error(f"RIPOSTE : suivi des journaux retabli (erreur precedente : {failing_since})")
                failing_since = None
        except OSError as error:  # base verrouillee, journal illisible... : jamais fatal
            message = f"{type(error).__name__} : {error}"
            if message != failing_since:
                report_error(f"RIPOSTE : suivi des journaux en erreur, nouvel essai au prochain tour : {message}")
                failing_since = message
        sleep(poll_seconds)
    store.set_state(STATE_STATS, current_stats())
    return stats
