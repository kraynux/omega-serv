"""Historique du tableau de bord web (lot 7) : sonde des compteurs de la machine et fichier de l'anneau."""
from __future__ import annotations

from typing import Any, Protocol

from omega_serv.domain.admin_web.history import Counters


class HistoryProbePort(Protocol):
    def read(self) -> Counters:
        """Compteurs cumules de la machine et lignes du journal d'acces ; peut bloquer : fil de travail."""
        ...

    def capacities(self) -> dict[str, Any]:
        """Tailles totales lues a l'affichage (memoire, swap, partition de l'instance, coeurs) et etat de la batterie,
        pour ecrire « utilise / total » a cote du pourcentage ; une valeur inconnue est absente."""
        ...


class HistoryStorePort(Protocol):
    def load(self) -> dict[str, Any] | None: ...

    def save(self, data: dict[str, Any]) -> None:
        """Peut lever OSError (dossier non inscriptible) : l'appelant garde l'historique en memoire."""
        ...
