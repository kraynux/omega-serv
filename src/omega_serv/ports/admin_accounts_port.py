"""Contrat du fichier des comptes de l'administration web (tableau de bord web, lot 3)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.admin_web.accounts import AdminAccount


class AdminAccountsPort(Protocol):
    def load(self) -> tuple[AdminAccount, ...]:
        ...

    def save(self, accounts: tuple[AdminAccount, ...]) -> None:
        ...
