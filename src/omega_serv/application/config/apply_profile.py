# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : `omega-serv profile apply` (spec §9.1).

Calcule le resultat (nouvelle configuration, diff, conflits, erreurs de
validation) SANS jamais ecrire de fichier - c'est a l'appelant
(interfaces/cli/) de decider s'il sauvegarde selon `has_blocking_issues`
et les options de la ligne de commande (--dry-run, --force), et
d'afficher le diff avant toute confirmation (spec decision #18 : jamais
un remplacement silencieux)."""
from __future__ import annotations

from dataclasses import dataclass, field

from omega_serv.domain.config.diff import ConfigChange, diff_configs
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.merge import compute_merged_config
from omega_serv.domain.config.profile import Profile
from omega_serv.domain.config.rules import ConfigConflict, detect_conflicts, has_blocking_conflicts
from omega_serv.domain.config.validation import validate_config


@dataclass
class ApplyProfileResult:
    new_config: OmegaServConfig
    changes: list[ConfigChange] = field(default_factory=list)
    conflicts: list[ConfigConflict] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.validation_errors) or has_blocking_conflicts(self.conflicts)


def plan_profile_application(current_config: OmegaServConfig, profile: Profile) -> ApplyProfileResult:
    new_config = compute_merged_config(profile, current_config.options)
    changes = diff_configs(current_config.to_dict(), new_config.to_dict())
    conflicts = detect_conflicts(new_config)
    validation_errors = validate_config(new_config)
    return ApplyProfileResult(
        new_config=new_config,
        changes=changes,
        conflicts=conflicts,
        validation_errors=validation_errors,
    )
