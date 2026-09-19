"""Contrat de lecture/ecriture du fichier de comptes (spec §15.2,
paths.auth_file)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.security.auth.entities import UserAccount


class UsersRepositoryPort(Protocol):
    def load(self) -> tuple[UserAccount, ...]:
        ...

    def save(self, users: tuple[UserAccount, ...]) -> None:
        ...
