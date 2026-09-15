# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage ObserveThreatCommand (plan_active_defense_omega_serv.md,
Phase 1) - traduit des decisions DEJA calculees (WafDecision/
ReputationDecision/ban connu) en une mise a jour de ThreatState,
jamais un second calcul de score independant sur la requete brute (voir
"Domaine metier" du plan). Decide de l'appel a ce cas d'usage (par
exemple : seulement quand war_mode est actif ET qu'un signal reel
existe) reste une responsabilite du site d'appel (cablage dans
infrastructure/server/asyncio_server.py, pas encore fait - Phase 1
"suite reelle"), jamais de ce module lui-meme."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from omega_serv.domain.security.active_defense.config import ActiveDefenseConfig
from omega_serv.domain.security.active_defense.entities import ThreatObservation, ThreatState
from omega_serv.domain.security.active_defense.events import ThreatEscalated
from omega_serv.domain.security.active_defense.policies import (
    OMEGA_FIRE_BAN_SCORE_DELTA,
    REPUTATION_ESCALATION_SCORE_DELTA,
    apply_observation,
    build_observation_from_waf_decision,
    level_rank,
)
from omega_serv.domain.security.active_defense.value_objects import AttackClass
from omega_serv.domain.security.waf.entities import WafDecision
from omega_serv.domain.security.waf.reputation import ReputationDecision
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort

_ObservationKind = Literal["waf_decision", "reputation_escalation", "blocklist_entry", "omega_fire_ban", "decoy_hit"]
"""Meme Literal exact que ThreatObservation.kind (domain/security/
active_defense/entities.py) - jamais un sous-ensemble narrower, sinon
mypy refuse d'assigner waf_observation.kind (type le plus large) ici."""


def _build_observation(
    subject_id: str,
    now: datetime,
    waf_decision: WafDecision | None,
    reputation_decision: ReputationDecision | None,
    known_ban: bool,
) -> ThreatObservation | None:
    """Les trois signaux sont ADDITIFS, jamais mutuellement exclusifs -
    un WafDecision bloquant ET un ban omega-fire deja connu peuvent
    survenir dans le MEME appel (le contraire serait une regression
    reelle : le score cumule ignorerait silencieusement l'un des deux).
    Un seul `ThreatObservation` est tout de meme retourne (le kind/
    attack_class le plus riche disponible sert de descripteur
    principal, `detail` combine toutes les raisons) - jamais un score_
    delta de 0 traite comme "quelque chose s'est produit" si aucun
    signal reel n'est present."""
    contributions: list[tuple[int, str]] = []
    kind: _ObservationKind | None = None
    attack_class: AttackClass = "unknown"

    if waf_decision is not None and waf_decision.score > 0:
        waf_observation = build_observation_from_waf_decision(subject_id, waf_decision, now)
        contributions.append((waf_observation.score_delta, waf_observation.detail))
        kind = waf_observation.kind
        attack_class = waf_observation.attack_class
    if reputation_decision is not None and reputation_decision.should_escalate:
        contributions.append((REPUTATION_ESCALATION_SCORE_DELTA, reputation_decision.reason))
        kind = kind or "reputation_escalation"
    if known_ban:
        contributions.append((OMEGA_FIRE_BAN_SCORE_DELTA, "ban omega-fire connu"))
        kind = kind or "omega_fire_ban"

    if not contributions or kind is None:
        return None
    return ThreatObservation(
        subject_id=subject_id,
        observed_at=now,
        kind=kind,
        attack_class=attack_class,
        score_delta=sum(delta for delta, _ in contributions),
        detail=" | ".join(detail for _, detail in contributions),
    )


def observe_threat(
    repository: ThreatStateRepositoryPort,
    clock: ClockPort,
    config: ActiveDefenseConfig,
    *,
    subject_id: str,
    waf_decision: WafDecision | None = None,
    reputation_decision: ReputationDecision | None = None,
    known_ban: bool = False,
) -> tuple[ThreatState, ThreatObservation | None, ThreatEscalated | None]:
    """Retourne le nouvel etat, l'observation construite (None si aucun
    signal reel - jamais un score_delta de 0 traite comme "quelque
    chose s'est produit", voir Phase 2) et un `ThreatEscalated`
    SEULEMENT si le niveau vient reellement d'augmenter (jamais emis
    sur une decroissance ou un niveau inchange - un evenement
    "escalade" n'a de sens que dans un seul sens)."""
    now = clock.now()
    current = repository.get(subject_id)
    previous_level = current.level if current is not None else "normal"
    previous_score = current.score if current is not None else 0
    last_updated_at = current.updated_at if current is not None else now

    observation = _build_observation(subject_id, now, waf_decision, reputation_decision, known_ban)
    score_delta = observation.score_delta if observation is not None else 0

    thresholds = config.war_mode.thresholds
    new_score, new_level = apply_observation(
        current_score=previous_score,
        last_updated_at=last_updated_at,
        now=now,
        score_delta=score_delta,
        suspicious_score=thresholds.suspicious_score,
        hostile_score=thresholds.hostile_score,
        contained_score=thresholds.contained_score,
        known_ban=known_ban,
    )

    new_state = ThreatState(
        subject_id=subject_id,
        score=new_score,
        level=new_level,
        updated_at=now,
        expires_at=now + timedelta(seconds=config.state_ttl_seconds),
        active_actions=current.active_actions if current is not None else (),
    )
    repository.save(new_state)

    escalation = None
    if level_rank(new_level) > level_rank(previous_level):
        escalation = ThreatEscalated(
            subject_id=subject_id, previous_level=previous_level, new_level=new_level, occurred_at=now,
        )
    return new_state, observation, escalation


def purge_expired_threat_states(repository: ThreatStateRepositoryPort, clock: ClockPort) -> int:
    """PurgeExpiredThreatStatesCommand - retourne le nombre d'entrees
    retirees."""
    return repository.expire_before(clock.now())
