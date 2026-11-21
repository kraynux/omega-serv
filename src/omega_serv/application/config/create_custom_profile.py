# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Creer un profil personnalise (projets 3.0.0 §B et §7.1). Rien n'est enregistre tant qu'il reste un trou
bloquant, un trou non accepte, une erreur d'identification ou une erreur de la configuration qui en resulterait."""
from __future__ import annotations

from dataclasses import dataclass, field

from omega_serv.application.config.apply_profile import plan_profile_application
from omega_serv.core.i18n import _
from omega_serv.domain.config.custom_profile import holes, identification_errors, profile_values
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.profile import Profile
from omega_serv.domain.config.rules import has_blocking_conflicts


@dataclass(frozen=True)
class CustomProfileCheck:
    field_errors: dict[str, str] = field(default_factory=dict)
    blocking: tuple[str, ...] = ()
    to_accept: tuple[tuple[str, str], ...] = ()
    """(code, message) des trous a accepter un par un."""
    not_accepted: tuple[str, ...] = ()

    @property
    def can_save(self) -> bool:
        return not self.field_errors and not self.blocking and not self.not_accepted


def check_custom_profile(name: str, label: str, description: str, selection: dict[str, str],
                         accepted: set[str], taken: set[str], current_config: OmegaServConfig) -> CustomProfileCheck:
    found = holes(selection)
    blocking = [hole.message for hole in found if hole.blocking]
    profile = build_custom_profile(name, label, description, selection, "")
    plan = plan_profile_application(current_config, profile)
    blocking += [_("Configuration refusée : {error}").format(error=error) for error in plan.validation_errors]
    if has_blocking_conflicts(plan.conflicts):
        blocking += [conflict.message for conflict in plan.conflicts if conflict.severity == "error"]
    to_accept = tuple((hole.code, hole.message) for hole in found if not hole.blocking)
    return CustomProfileCheck(
        field_errors=identification_errors(name, label, description, taken),
        blocking=tuple(blocking), to_accept=to_accept,
        not_accepted=tuple(code for code, _message in to_accept if code not in accepted),
    )


def build_custom_profile(name: str, label: str, description: str, selection: dict[str, str],
                         created_at: str) -> Profile:
    return Profile(name=name, description=description.strip(), values=profile_values(selection),
                   label=label.strip(), custom=True, selection=dict(selection), created_at=created_at)
