"""Contrat d'acces aux profils nommes (config/profiles/*.json)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from omega_serv.domain.config.profile import Profile


class ProfileRepositoryPort(Protocol):
    def list_profile_names(self) -> list[str]:
        ...

    def load_profile(self, name: str) -> Profile:
        """Raises:
            ProfileNotFoundError: si aucun fichier ne correspond au nom.
            ProfileLoadError: si le fichier existe mais est illisible ou
                syntaxiquement invalide.
        """
        ...

    def provided_profile_names(self) -> list[str]:
        """Profils livres avec omega-serv (jamais modifiables ni supprimables)."""
        ...

    def save_custom_profile(self, profile: Profile) -> Path:
        """Profil personnalise (config/profiles/custom/<nom>.json, 2026-11-15)."""
        ...

    def delete_custom_profile(self, name: str) -> bool:
        ...
