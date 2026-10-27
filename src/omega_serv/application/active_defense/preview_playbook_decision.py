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
from omega_serv.core.i18n import _
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
        _("Score projeté : {previous_score} -> {projected_score} (delta={score_delta:+d}).").format(previous_score=previous_score, projected_score=projected_score, score_delta=score_delta),
        _("Niveau projeté : {previous_level} -> {projected_level}.").format(previous_level=previous_level, projected_level=projected_level),
    ]

    would_escalate = projected_level != previous_level
    if not config.war_mode.enabled:
        explanation.append(_("war_mode désactivé : aucune action ne se déclencherait réellement."))

    would_create_incident = False
    if config.war_mode.enabled and validate_playbook_action("create_incident", playbook):
        has_open_incident = incident_repository.find_open_id_for(subject_id) is not None
        transition = decide_incident_transition(
            has_open_incident, projected_score, incident_score_threshold=thresholds.incident_score,
        )
        would_create_incident = transition != "no_change"
        explanation.append(_("Incident : {transition}.").format(transition=transition))
    else:
        explanation.append(_("Incident : action 'create_incident' absente du playbook ou war_mode désactivé."))

    would_assign_deception = False
    selected_decoy_profile: str | None = None
    if (
        config.war_mode.enabled
        and config.deception.enabled
        and validate_playbook_action("redirect_to_decoy", playbook)
        and projected_level in ("hostile", "contained")
    ):
        if deception_assignment_repository.get(subject_id) is not None:
            explanation.append(_("Deception : une affectation existe déjà pour cette source."))
        else:
            profile = select_decoy_profile(attack_class, profiles_from_config(config.deception))
            if profile is not None:
                would_assign_deception = True
                selected_decoy_profile = profile.name
                explanation.append(_("Deception : leurre {name!r} serait affecté.").format(name=profile.name))
            else:
                explanation.append(_("Deception : aucun profil actif ne correspond à {attack_class!r}.").format(attack_class=attack_class))
    else:
        explanation.append(_("Deception : conditions non réunies (niveau, deception ou playbook)."))

    marked = is_source_marked(projected_level)
    would_enrich_log = (
        config.war_mode.enabled and marked and validate_playbook_action("enrich_log", playbook)
    )
    explanation.append(
        _("Journalisation enrichie : ")
        + ("declenchee." if would_enrich_log else _("non déclenchée (source non marquée ou action absente)."))
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
            _("Ralentissement : entre {minimum_ms} et {maximum_ms} ms.").format(minimum_ms=config.war_mode.slowdown.minimum_ms, maximum_ms=config.war_mode.slowdown.maximum_ms)
        )
    else:
        explanation.append(_("Ralentissement : non déclenché (source non marquée, action absente ou désactivé)."))

    would_rate_limit = config.war_mode.enabled and marked and validate_playbook_action("rate_limit", playbook)
    explanation.append(
        _("Limitation de débit : ")
        + ("appliquee." if would_rate_limit else _("non appliquée (source non marquée ou action absente)."))
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
