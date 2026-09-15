# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Exceptions du domaine configuration."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class ConfigError(OmegaServError):
    """Racine des erreurs de configuration."""


class ConfigLoadError(ConfigError):
    """Le fichier de configuration est absent, illisible ou
    syntaxiquement invalide (JSON malforme)."""


class ConfigValidationError(ConfigError):
    """La configuration chargee ne respecte pas les regles de
    validite structurelle (domain/config/validation.py)."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class ProfileNotFoundError(ConfigError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Profil introuvable : {name}")


class ProfileLoadError(ConfigError):
    """Le fichier de profil est illisible ou syntaxiquement invalide."""
