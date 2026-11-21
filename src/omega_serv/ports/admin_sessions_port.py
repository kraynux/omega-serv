"""Sessions ouvertes du panneau web vues depuis la TUI (etude modules, module 5) : liste publiee par le processus
d'administration (sans jeton) et demandes de fermeture deposees par la TUI."""
from __future__ import annotations

from typing import Any, Protocol


class SessionFilesPort(Protocol):
    def publish(self, sessions: list[dict[str, Any]]) -> None: ...

    def published(self) -> tuple[float, list[dict[str, Any]]] | None:
        """(moment de publication, sessions) ; None si rien n'a ete publie."""
        ...

    def request_close(self, public_id: str) -> None: ...

    def take_close_requests(self) -> list[str]:
        """Demandes deposees par la TUI, retirees a la lecture ; jamais d'exception."""
        ...
