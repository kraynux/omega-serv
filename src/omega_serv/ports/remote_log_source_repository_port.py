"""Contrat des sources distantes (SSH) de logs (OMEGA-SERV_ETUDE-
FAISABILITE_LOGS_DISTANTS.md, 2026-10-15) : definitions nommees
(label/hote/chemin distant/...), source = saisie manuelle de
l'utilisateur, recuperation a la demande depuis l'ecran dedie."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.logs.remote_source import RemoteLogSource


class RemoteLogSourceRepositoryPort(Protocol):
    def list_all(self) -> list[RemoteLogSource]: ...

    def add(self, source: RemoteLogSource) -> None: ...

    def remove(self, label: str) -> None: ...
