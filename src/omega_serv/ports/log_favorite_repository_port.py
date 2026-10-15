"""Contrat des Favoris de logs (gestion des logs, refonte menu
2026-10-15) : combinaisons logs+viewer nommees, source = Bibliotheque,
lancement direct depuis l'ecran Favoris."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.logs.favorite import Favorite


class LogFavoriteRepositoryPort(Protocol):
    def list_all(self) -> list[Favorite]: ...

    def add(self, favorite: Favorite) -> None: ...

    def remove(self, name: str) -> None: ...
