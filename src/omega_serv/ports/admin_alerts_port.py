"""Alertes locales du panneau web (etude modules, module 1) : etat des alertes, journal, maintenance."""
from __future__ import annotations

from typing import Any, Protocol


class AlertStorePort(Protocol):
    def load(self) -> dict[str, Any] | None: ...

    def save(self, data: dict[str, Any]) -> None:
        """Peut lever OSError : l'appelant garde les alertes en memoire."""
        ...

    def log(self, line: str) -> None:
        """Une ligne de var/log/alertes.log ; jamais d'exception."""
        ...

    def maintenance_until(self) -> float | None: ...

    def set_maintenance(self, until: float | None) -> None: ...
