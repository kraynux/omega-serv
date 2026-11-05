"""Traitement des evenements par le processus RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.3-3.6).

Pour chaque evenement, dans l'ordre chronologique : memoire de la source mise a jour, decision unique
(domain/security/riposte/decide.py), puis enregistrement de ce qui est significatif (action decidee,
refus des garde-fous, arret). Le temps de reference de la DECISION est la date de l'evenement (comme la
mesure, qui rejoue des journaux) ; une action appliquee court a partir de maintenant (horloge).

Lot 4 : avec un `actuator`, une decision « agir » est APPLIQUEE (registre, puis blocklist ou leurre) ;
une action reellement en place compte pour le palier suivant (sauf un leurre). Sans `actuator` (tests,
comportement du lot 3) : decision enregistree, jamais appliquee. Plafonds (`max_active_bans`, actions
par source) et exemptions ajoutees par « Lever et exempter » sont lus dans le registre."""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timedelta

from omega_serv.application.riposte.actuator import RiposteActuator
from omega_serv.domain.security.riposte.actions import MAX_FINISHED_ACTIONS
from omega_serv.domain.security.riposte.config import RiposteConfig
from omega_serv.domain.security.riposte.decide import Decision, SafetyContext, decide
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.domain.security.riposte.history import (
    PastAction,
    SourceHistory,
    apply_event,
    forget_before,
    mark_episode_decided,
    record_action,
)
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.riposte_store_port import RiposteStorePort

STATE_EMERGENCY_STOP = "emergency_stop"
MAX_SOURCES = 200_000
"""Meme ordre de grandeur que les sources suivies par Active Defense (MAX_TRACKED_SUBJECTS)."""
DECISIONS_RETENTION = timedelta(days=90)
MAX_DECISIONS = 100_000
RECORDED_STATUSES = frozenset({"matched", "rejected_by_safety", "stopped"})
FINISHED_ACTIONS_RETENTION = timedelta(days=90)


class RiposteEngine:
    def __init__(
        self,
        store: RiposteStorePort,
        config: RiposteConfig,
        exempt_networks: tuple[str, ...],
        *,
        actuator: RiposteActuator | None = None,
        clock: ClockPort | None = None,
    ) -> None:
        self._store = store
        self._config = config
        self._exempt_networks = exempt_networks
        self._actuator = actuator
        self._clock = clock
        self.decisions: Counter[str] = Counter()
        self.actions: Counter[str] = Counter()

    def update_config(self, config: RiposteConfig, exempt_networks: tuple[str, ...]) -> None:
        """Rechargement (SIGHUP) : nouvelles politiques pour les evenements suivants, memoire conservee."""
        self._config = config
        self._exempt_networks = exempt_networks

    def handle(self, events: Sequence[ObservedEvent]) -> list[Decision]:
        recorded: list[Decision] = []
        emergency_stop = self._store.get_state(STATE_EMERGENCY_STOP) == "1"
        exempt_networks = self._current_exemptions()
        for event in sorted(events, key=lambda e: e.timestamp):
            history = self._store.get_source(event.remote_ip) or SourceHistory(event.remote_ip)
            # Retention (90 j) appliquee aussi a une source qui reste active : jamais une memoire sans fin.
            history = forget_before(history, event.timestamp - timedelta(seconds=self._config.history_retention_seconds))
            history, _new_episode = apply_event(history, event, episode_gap_seconds=self._config.episode_gap_seconds)
            safety = SafetyContext(
                exempt_networks=exempt_networks, emergency_stop=emergency_stop,
                active_total=self._store.count_in_progress(bans_only=True) if self._actuator else 0,
                active_for_source=(
                    self._store.count_in_progress(bans_only=False, ip=event.remote_ip) if self._actuator else 0
                ),
            )
            decision = decide(history, event, self._config, safety, event.timestamp)
            self.decisions[decision.status] += 1
            applied = False
            if decision.status == "matched":
                history, applied = self._act(decision, history)
            if decision.status in RECORDED_STATUSES:
                self._store.append_decision(decision, applied=applied)
                recorded.append(decision)
            self._store.save_source(history, event.timestamp)
        return recorded

    def _act(self, decision: Decision, history: SourceHistory) -> tuple[SourceHistory, bool]:
        if self._actuator is None or self._clock is None:
            return mark_episode_decided(history), False
        action = self._actuator.apply(decision, history.subject_ids, self._clock.now())
        self.actions[action.state if action.state != "failed" else f"failed:{action.detail}"] += 1
        if action.state != "applied":
            return mark_episode_decided(history), False
        assert action.policy_id is not None
        return record_action(history, PastAction(
            taken_at=action.created_at, ends_at=action.ends_at, policy_id=action.policy_id,
            tier_index=action.tier_index if action.tier_index is not None else 0,
            counts_for_recidive=action.counts_for_recidive, action_id=action.id,
        )), True

    def _current_exemptions(self) -> tuple[str, ...]:
        if self._actuator is None or self._clock is None:
            return self._exempt_networks
        now = self._clock.now()
        added = tuple(e.network for e in self._store.list_exemptions() if e.active(now))
        return (*self._exempt_networks, *(n for n in added if n not in self._exempt_networks))

    def maintenance(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self._config.history_retention_seconds)
        self._store.purge_sources(cutoff, MAX_SOURCES)
        self._store.purge_decisions(now - DECISIONS_RETENTION, MAX_DECISIONS)
        self._store.purge_finished_actions(now - FINISHED_ACTIONS_RETENTION, MAX_FINISHED_ACTIONS)
        self._store.purge_exemptions(now)
