"""Statistiques de trafic du panneau web (etude modules, module 2) : un fichier par jour sous var/lib/admin/stats/."""
from __future__ import annotations

from typing import Any, Protocol


class StatsStorePort(Protocol):
    def load(self, day: str) -> dict[str, Any] | None: ...

    def save(self, day: str, data: dict[str, Any]) -> None:
        """Peut lever OSError : l'appelant garde le jour en memoire."""
        ...

    def days(self) -> list[str]:
        """Jours enregistres (AAAA-MM-JJ), du plus ancien au plus recent."""
        ...

    def remove(self, day: str) -> None: ...
