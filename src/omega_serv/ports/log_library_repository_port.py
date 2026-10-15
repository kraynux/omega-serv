"""Contrat de la Bibliotheque de logs (gestion des logs, refonte menu
2026-10-15) : hub central referencant tous les logs a traiter, alimente
manuellement (voir `domain/logs/library.py`)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.logs.library import LibraryRecord


class LogLibraryRepositoryPort(Protocol):
    def list_all(self) -> list[LibraryRecord]: ...

    def add(self, record: LibraryRecord) -> None: ...

    def remove(self, path: str) -> None: ...

    def contains(self, path: str) -> bool: ...
