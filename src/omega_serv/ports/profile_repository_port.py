# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat d'acces aux profils nommes (config/profiles/*.json)."""
from __future__ import annotations

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
