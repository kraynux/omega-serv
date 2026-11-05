"""Decision RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.5, lot 3). Pur, et UNIQUE : la meme fonction
sert au processus, a « Simuler » et a « Mesurer » (etude §18.4 : la simulation doit etre identique a
l'execution, aux effets de bord pres).

Ordre (etude §6.4) : arret d'urgence -> exclusions -> une seule action par episode -> premiere politique
active dont toutes les conditions sont remplies (ordre de la configuration) -> plafonds -> palier.

L'explication est une suite de `Reason` (code + parametres), jamais du texte : l'interface les traduit
(17 langues). Chaque decision dit quel evenement, quelle politique, quelles conditions, quelles
exclusions verifiees, quelle action et quelle duree - ou pourquoi rien."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from omega_serv.domain.security.riposte.config import RiposteConfig, RipostePolicy
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.domain.security.riposte.history import (
    LEVEL_RANK,
    SourceHistory,
    episodes_since,
    next_tier_index,
)
from omega_serv.domain.security.waf.reputation import is_exempt_from_auto_block

DecisionStatus = Literal["stopped", "rejected_by_safety", "observed", "matched"]
DECIDING_KINDS = frozenset({"attack", "decoy_hit", "threat_escalated"})
"""Seuls ces evenements peuvent declencher une decision (jamais un refus de blocklist : anti-boucle)."""
BAN_ACTIONS = frozenset({"local_ban", "local_and_network_ban"})


@dataclass(frozen=True)
class Reason:
    code: str
    params: tuple[tuple[str, str | int], ...] = ()

    def param(self, key: str) -> str | int | None:
        return dict(self.params).get(key)


def _reason(code: str, **params: str | int) -> Reason:
    return Reason(code, tuple(sorted(params.items())))


@dataclass(frozen=True)
class SafetyContext:
    """Ce que la decision doit savoir de l'exterieur, fourni par l'appelant."""
    exempt_networks: tuple[str, ...]
    """Exclusions du WAF telles qu'appliquees (effective_never_auto_block) + exemptions RIPOSTE."""
    active_total: int = 0
    """Bans RIPOSTE actuellement en vigueur (plafond `max_active_bans`)."""
    active_for_source: int = 0
    emergency_stop: bool = False


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    ip: str
    event_id: str
    decided_at: datetime
    policy_id: str | None = None
    action: str | None = None
    tier_index: int | None = None
    duration_seconds: int | None = None
    decoy_profile: str | None = None
    reasons: tuple[Reason, ...] = field(default_factory=tuple)


def _exempting_network(ip: str, networks: tuple[str, ...]) -> str | None:
    for network in networks:
        if is_exempt_from_auto_block(ip, (network,)):
            return network
    return None


def _first_unmet_condition(policy: RipostePolicy, history: SourceHistory, now: datetime) -> Reason | None:
    episode = history.current_episode
    assert episode is not None
    returns = episodes_since(history, now - timedelta(seconds=policy.within_seconds))
    if returns < policy.returns:
        return _reason("unmet_returns", policy=policy.id, have=returns, need=policy.returns,
                       within_seconds=policy.within_seconds)
    if policy.attack_classes and not set(policy.attack_classes) & set(episode.attack_classes):
        return _reason("unmet_attack_class", policy=policy.id, need=",".join(policy.attack_classes),
                       have=",".join(episode.attack_classes) or "-")
    if policy.min_ad_level is not None and (
        episode.max_level is None or LEVEL_RANK.get(episode.max_level, -1) < LEVEL_RANK[policy.min_ad_level]
    ):
        return _reason("unmet_level", policy=policy.id, need=policy.min_ad_level, have=episode.max_level or "-")
    if policy.decoy_hits and episode.decoy_hits < policy.decoy_hits:
        return _reason("unmet_decoy_hits", policy=policy.id, have=episode.decoy_hits, need=policy.decoy_hits)
    return None


def decide(
    history: SourceHistory, event: ObservedEvent, config: RiposteConfig, safety: SafetyContext, now: datetime,
) -> Decision:
    def result(
        status: DecisionStatus, reasons: list[Reason], *, policy_id: str | None = None, action: str | None = None,
        tier_index: int | None = None, duration_seconds: int | None = None, decoy_profile: str | None = None,
    ) -> Decision:
        return Decision(
            status=status, ip=history.ip, event_id=event.event_id, decided_at=now, policy_id=policy_id,
            action=action, tier_index=tier_index, duration_seconds=duration_seconds, decoy_profile=decoy_profile,
            reasons=tuple(reasons),
        )

    reasons = [_reason("event", kind=event.kind, ip=event.remote_ip)]
    if event.kind not in DECIDING_KINDS:
        return result("observed", [*reasons, _reason("not_a_deciding_event")])
    if safety.emergency_stop:
        return result("stopped", [*reasons, _reason("emergency_stop")])
    network = _exempting_network(history.ip, safety.exempt_networks)
    if network is not None:
        return result("rejected_by_safety", [*reasons, _reason("exempt_network", network=network)])
    reasons.append(_reason("exemptions_checked", count=len(safety.exempt_networks)))
    episode = history.current_episode
    if episode is None:
        return result("observed", [*reasons, _reason("no_episode")])
    if episode.action_taken:
        return result("observed", [*reasons, _reason("already_acted_this_episode")])

    unmet: list[Reason] = []
    matched: RipostePolicy | None = None
    for policy in config.policies:
        if not policy.enabled:
            unmet.append(_reason("policy_disabled", policy=policy.id))
            continue
        failure = _first_unmet_condition(policy, history, now)
        if failure is None:
            matched = policy
            break
        unmet.append(failure)
    if matched is None:
        return result("observed", [*reasons, *unmet, _reason("no_policy_matched", policies=len(config.policies))])

    reasons += [*unmet, _reason("policy_matched", policy=matched.id)]
    if safety.active_for_source >= matched.max_active_per_source:
        return result("rejected_by_safety", [*reasons, _reason("source_already_has_action",
                      current=safety.active_for_source, limit=matched.max_active_per_source)], policy_id=matched.id)
    if matched.action in BAN_ACTIONS and safety.active_total >= config.max_active_bans:
        return result("rejected_by_safety", [*reasons, _reason("max_active_bans_reached",
                      current=safety.active_total, limit=config.max_active_bans)], policy_id=matched.id)

    if matched.action == "decoy":
        duration = matched.decoy_duration_seconds
        return result("matched", [*reasons, _reason("decoy", profile=matched.decoy_profile or "-", duration=duration)],
                      policy_id=matched.id, action=matched.action, duration_seconds=duration,
                      decoy_profile=matched.decoy_profile)
    tiers = matched.tiers_seconds or config.tiers_seconds
    index = next_tier_index(history, now, recidive_window_seconds=config.recidive_window_seconds, tier_count=len(tiers))
    return result("matched", [*reasons, _reason("tier", index=index + 1, of=len(tiers), duration=tiers[index])],
                  policy_id=matched.id, action=matched.action, tier_index=index, duration_seconds=tiers[index])
