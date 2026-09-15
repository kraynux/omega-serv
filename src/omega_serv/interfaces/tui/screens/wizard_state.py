# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Etat partage entre les ecrans de l'assistant premier lancement (plan
interface §11) - transmis d'ecran en ecran, jamais persiste : rien n'est
ecrit sur disque avant l'etape Resume (etape 7), meme discipline "diff
avant ecriture" que le reste du projet (ApplyProfileScreen, etc.)."""
from __future__ import annotations

from dataclasses import dataclass, field

from omega_serv.domain.config.defaults import builtin_safe_defaults
from omega_serv.domain.config.entities import OmegaServConfig


@dataclass
class WizardState:
    profile_name: str = ""
    config: OmegaServConfig = field(default_factory=builtin_safe_defaults)
    self_signed_public_bind_confirmed: bool = False
    auth_without_tls_confirmed: bool = False
