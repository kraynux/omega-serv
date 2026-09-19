"""Contrat d'acces au registre multi-instance global (OMEGA-SERV_PLAN-
DETAILLE_MULTI_INSTANCE.md §3) - meme patron que ProfileRepositoryPort,
mais un seul fichier JSON contenant une liste plutot qu'un dossier de
fichiers nommes."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.instances.entities import InstanceEntry


class InstanceRegistryPort(Protocol):
    def load(self) -> list[InstanceEntry]:
        ...

    def save(self, entries: list[InstanceEntry]) -> None:
        ...
