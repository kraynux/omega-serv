"""« Mesurer » une politique (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.10, topo §6.5, lot 3) : rejouer les
journaux disponibles avec la MEME decision que le processus (domain/security/riposte/decide.py), en
memoire, sans rien ecrire. Les actions decidees pendant le rejeu sont « simulees » : elles font monter
les paliers et comptent dans les plafonds exactement comme elles le feraient en reel.

Resultat honnete : la periode reellement couverte par les journaux est rendue (« mesure sur 4 j »), et
un rejeu tronque (trop d'evenements) le dit."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from omega_serv.domain.security.riposte.config import RiposteConfig
from omega_serv.domain.security.riposte.decide import SafetyContext, decide
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.domain.security.riposte.history import (
    PastAction,
    SourceHistory,
    apply_event,
    record_action,
)

MAX_MEASURE_EVENTS = 500_000
"""Au-dela, seuls les plus recents sont rejoues (memoire bornee) et le resultat est marque tronque."""


@dataclass
class MeasureResult:
    events: int = 0
    actions: int = 0
    sources_acted: set[str] = field(default_factory=set)
    rejected_by_safety: int = 0
    max_cumulative_ban_seconds: int = 0
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    truncated: bool = False
    by_policy: dict[str, int] = field(default_factory=dict)


def measure(
    events: Iterable[ObservedEvent], config: RiposteConfig, exempt_networks: tuple[str, ...],
    *, since: datetime | None = None,
) -> MeasureResult:
    selected = [e for e in events if since is None or e.timestamp >= since]
    result = MeasureResult()
    if len(selected) > MAX_MEASURE_EVENTS:
        selected.sort(key=lambda e: e.timestamp)
        selected = selected[-MAX_MEASURE_EVENTS:]
        result.truncated = True
    selected.sort(key=lambda e: e.timestamp)
    histories: dict[str, SourceHistory] = {}
    active: dict[str, list[datetime]] = {}  # ip -> fins des actions simulees encore en cours
    cumulative: dict[str, int] = {}
    for event in selected:
        now = event.timestamp
        result.events += 1
        result.first_event_at = result.first_event_at or now
        result.last_event_at = now
        history = histories.get(event.remote_ip) or SourceHistory(event.remote_ip)
        history, _ = apply_event(history, event, episode_gap_seconds=config.episode_gap_seconds)
        for ip in list(active):
            active[ip] = [end for end in active[ip] if end > now]
        safety = SafetyContext(
            exempt_networks=exempt_networks,
            active_total=sum(len(ends) for ends in active.values()),
            active_for_source=len(active.get(event.remote_ip, ())),
        )
        decision = decide(history, event, config, safety, now)
        if decision.status == "rejected_by_safety":
            result.rejected_by_safety += 1
        elif decision.status == "matched" and decision.duration_seconds is not None and decision.policy_id is not None:
            ends = now + timedelta(seconds=decision.duration_seconds)
            is_ban = decision.action != "decoy"
            history = record_action(history, PastAction(
                taken_at=now, ends_at=ends, policy_id=decision.policy_id,
                tier_index=decision.tier_index or 0, counts_for_recidive=is_ban,
            ))
            active.setdefault(event.remote_ip, []).append(ends)
            result.actions += 1
            result.sources_acted.add(event.remote_ip)
            result.by_policy[decision.policy_id] = result.by_policy.get(decision.policy_id, 0) + 1
            if is_ban:
                cumulative[event.remote_ip] = cumulative.get(event.remote_ip, 0) + decision.duration_seconds
                result.max_cumulative_ban_seconds = max(result.max_cumulative_ban_seconds, cumulative[event.remote_ip])
        histories[event.remote_ip] = history
    return result
