# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage AssignDeceptionCommand/ReleaseDeceptionCommand et
resolution de RoutingDecision (plan_active_defense_omega_serv.md,
Phase 3)."""
from __future__ import annotations

from datetime import timedelta
from typing import cast

from omega_serv.domain.security.active_defense.config import DeceptionConfig
from omega_serv.domain.security.active_defense.entities import (
    DeceptionAssignment,
    DeceptionProfile,
    RoutingDecision,
)
from omega_serv.domain.security.active_defense.policies import (
    is_assignment_active,
    select_decoy_profile,
)
from omega_serv.domain.security.active_defense.value_objects import AttackClass
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.deception_assignment_repository_port import DeceptionAssignmentRepositoryPort


def profiles_from_config(config: DeceptionConfig) -> tuple[DeceptionProfile, ...]:
    """`profile.match_attack_classes` est un tuple[str, ...] issu du JSON de
    config - le cast() ci-dessous est sans risque car
    validate_active_defense_config() a deja rejete toute valeur hors de
    KNOWN_ATTACK_CLASSES avant que cette configuration n'atteigne ce code
    (jamais invoque sur une config non validee)."""
    return tuple(
        DeceptionProfile(
            name=name,
            enabled=profile.enabled,
            match_attack_classes=cast("tuple[AttackClass, ...]", tuple(profile.match_attack_classes)),
            isolation_level=profile.isolation_level,
            reverse_proxy_zone_name=profile.reverse_proxy_zone_name,
        )
        for name, profile in config.profiles.items()
    )


def assign_deception(
    assignment_repository: DeceptionAssignmentRepositoryPort,
    clock: ClockPort,
    config: DeceptionConfig,
    *,
    subject_id: str,
    attack_class: AttackClass,
) -> DeceptionAssignment | None:
    """AssignDeceptionCommand - retourne None si la deception est
    desactivee, si une affectation existe deja (V1 : jamais de
    changement de profil en cours de route pour une meme source), ou si
    aucun profil active ne correspond a la classe d'attaque observee."""
    if not config.enabled:
        return None
    if assignment_repository.get(subject_id) is not None:
        return None
    profile = select_decoy_profile(attack_class, profiles_from_config(config))
    if profile is None:
        return None
    now = clock.now()
    assignment = DeceptionAssignment(
        subject_id=subject_id, profile_name=profile.name, assigned_at=now,
        expires_at=now + timedelta(seconds=config.assignments_ttl_seconds),
    )
    assignment_repository.save(assignment)
    return assignment


def release_deception(assignment_repository: DeceptionAssignmentRepositoryPort, subject_id: str) -> None:
    """ReleaseDeceptionCommand - jamais une erreur si aucune affectation
    n'existait deja (idempotent, meme regle que close_incident)."""
    assignment_repository.release(subject_id)


def resolve_routing_decision(
    assignment_repository: DeceptionAssignmentRepositoryPort, clock: ClockPort, config: DeceptionConfig, subject_id: str,
) -> RoutingDecision:
    """Decide si CETTE requete doit etre deroutee vers un leurre -
    appelee pour CHAQUE requete quand `deception.enabled`, jamais
    seulement celles qui declenchent une observation WAF (une source
    deja affectee doit recevoir le leurre sur n'importe quel chemin
    ensuite, cf. plan §"Deception dynamique").

    Phase 5 ("Niveau 2") : le PROFIL affecte (pas seulement l'affectation
    elle-meme) determine le niveau d'isolation - `isolation_level ==
    "proxy"` retourne `decoy_proxy` (reverse_proxy_zone_name resolu
    contre `config.deception.decoy_zones`, jamais `options.reverse_proxy`,
    voir "Routage vers les leurres"), sinon `decoy_fixture` (Niveau 1,
    comportement Phase 3 inchange). Si le profil a disparu de la config
    depuis l'affectation (rare : reload/edition manuelle), retombe sur
    `decoy_fixture` plutot que de planter - le dispatcher de fixtures
    gere deja un profil inconnu en retournant None (fallback applique
    par l'appelant)."""
    assignment = assignment_repository.get(subject_id)
    if assignment is None or not is_assignment_active(assignment, clock.now()):
        return RoutingDecision(kind="production")
    profile_config = config.profiles.get(assignment.profile_name)
    if profile_config is not None and profile_config.isolation_level == "proxy":
        return RoutingDecision(
            kind="decoy_proxy", deception_profile_name=assignment.profile_name,
            reverse_proxy_zone_name=profile_config.reverse_proxy_zone_name,
        )
    return RoutingDecision(kind="decoy_fixture", deception_profile_name=assignment.profile_name)
