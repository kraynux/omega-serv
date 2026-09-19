"""PreviewPlaybookDecisionQuery (plan_active_defense_omega_serv.md,
Phase 4 : "ajouter simulation, dry-run et explication de la decision
dans CLI/TUI"). Lecture seule stricte : lit l'etat courant (s'il
existe) via les repositories, applique les MEMES fonctions pures que
les commandes reelles (`apply_observation`/`select_decoy_profile`/
`validate_playbook_action`/`decide_incident_transition`), mais
n'appelle JAMAIS `.save()`/`.create()`/`.add_event()` sur un
repository - une observation synthetique ne doit jamais laisser de
trace (plan §"Ecrans TUI", "Simulation" : "sans impact reseau", ce qui
inclut sans impact sur l'etat persiste)."""
from __future__ import annotations

from omega_serv.application.active_defense.manage_deception import profiles_from_config
from omega_serv.domain.security.active_defense.config import ActiveDefenseConfig
from omega_serv.domain.security.active_defense.entities import PlaybookPreview
from omega_serv.domain.security.active_defense.policies import (
    apply_observation,
    build_playbook,
    decide_incident_transition,
    is_source_marked,
    select_decoy_profile,
    validate_playbook_action,
)
from omega_serv.domain.security.active_defense.value_objects import AttackClass
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.deception_assignment_repository_port import DeceptionAssignmentRepositoryPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort


def preview_playbook_decision(
    threat_state_repository: ThreatStateRepositoryPort,
    incident_repository: IncidentRepositoryPort,
    deception_assignment_repository: DeceptionAssignmentRepositoryPort,
    clock: ClockPort,
    config: ActiveDefenseConfig,
    *,
    subject_id: str,
    attack_class: AttackClass,
    score_delta: int,
) -> PlaybookPreview:
    now = clock.now()
    current = threat_state_repository.get(subject_id)
    previous_score = current.score if current is not None else 0
    previous_level = current.level if current is not None else "normal"
    last_updated_at = current.updated_at if current is not None else now

    thresholds = config.war_mode.thresholds
    projected_score, projected_level = apply_observation(
        current_score=previous_score,
        last_updated_at=last_updated_at,
        now=now,
        score_delta=score_delta,
        suspicious_score=thresholds.suspicious_score,
        hostile_score=thresholds.hostile_score,
        contained_score=thresholds.contained_score,
        known_ban=False,
    )
    playbook = build_playbook(config.war_mode)
    explanation: list[str] = [
        f"Score projete : {previous_score} -> {projected_score} (delta={score_delta:+d}).",
        f"Niveau projete : {previous_level} -> {projected_level}.",
    ]

    would_escalate = projected_level != previous_level
    if not config.war_mode.enabled:
        explanation.append("war_mode desactive : aucune action ne se declencherait reellement.")

    would_create_incident = False
    if config.war_mode.enabled and validate_playbook_action("create_incident", playbook):
        existing = incident_repository.find_open_for(subject_id)
        transition = decide_incident_transition(
            existing, projected_score, incident_score_threshold=thresholds.incident_score,
        )
        would_create_incident = transition != "no_change"
        explanation.append(f"Incident : {transition}.")
    else:
        explanation.append("Incident : action 'create_incident' absente du playbook ou war_mode desactive.")

    would_assign_deception = False
    selected_decoy_profile: str | None = None
    if (
        config.war_mode.enabled
        and config.deception.enabled
        and validate_playbook_action("redirect_to_decoy", playbook)
        and projected_level in ("hostile", "contained")
    ):
        if deception_assignment_repository.get(subject_id) is not None:
            explanation.append("Deception : une affectation existe deja pour cette source.")
        else:
            profile = select_decoy_profile(attack_class, profiles_from_config(config.deception))
            if profile is not None:
                would_assign_deception = True
                selected_decoy_profile = profile.name
                explanation.append(f"Deception : leurre {profile.name!r} serait affecte.")
            else:
                explanation.append(f"Deception : aucun profil actif ne correspond a {attack_class!r}.")
    else:
        explanation.append("Deception : conditions non reunies (niveau, deception ou playbook).")

    marked = is_source_marked(projected_level)
    would_enrich_log = (
        config.war_mode.enabled and marked and validate_playbook_action("enrich_log", playbook)
    )
    explanation.append(
        "Journalisation enrichie : "
        + ("declenchee." if would_enrich_log else "non declenchee (source non marquee ou action absente).")
    )

    would_delay = (
        config.war_mode.enabled
        and marked
        and config.war_mode.slowdown.enabled
        and validate_playbook_action("delay", playbook)
    )
    delay_range_ms = (
        (config.war_mode.slowdown.minimum_ms, config.war_mode.slowdown.maximum_ms) if would_delay else None
    )
    if would_delay:
        explanation.append(
            f"Ralentissement : entre {config.war_mode.slowdown.minimum_ms} et "
            f"{config.war_mode.slowdown.maximum_ms} ms."
        )
    else:
        explanation.append("Ralentissement : non declenche (source non marquee, action absente ou desactive).")

    would_rate_limit = config.war_mode.enabled and marked and validate_playbook_action("rate_limit", playbook)
    explanation.append(
        "Limitation de debit : "
        + ("appliquee." if would_rate_limit else "non appliquee (source non marquee ou action absente).")
    )

    return PlaybookPreview(
        subject_id=subject_id,
        previous_score=previous_score,
        previous_level=previous_level,
        projected_score=projected_score,
        projected_level=projected_level,
        would_escalate=would_escalate,
        would_create_incident=would_create_incident,
        would_assign_deception=would_assign_deception,
        selected_decoy_profile=selected_decoy_profile,
        would_enrich_log=would_enrich_log,
        would_delay=would_delay,
        delay_range_ms=delay_range_ms,
        would_rate_limit=would_rate_limit,
        explanation=tuple(explanation),
    )
