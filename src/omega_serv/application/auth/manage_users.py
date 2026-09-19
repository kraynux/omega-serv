"""Cas d'usage `omega-serv auth add-user/remove-user/change-password`
(spec §15.3/§15.4). Le mot de passe en clair ne transite jamais au-dela
de ce module (immediatement hache, jamais journalise)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.security.auth.entities import UserAccount
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.ports.users_repository_port import UsersRepositoryPort


@dataclass(frozen=True)
class ManageUsersResult:
    success: bool
    message: str


def add_user(users_repo: UsersRepositoryPort, username: str, password: str) -> ManageUsersResult:
    if not username:
        return ManageUsersResult(False, "username ne peut pas etre vide")
    if not password:
        return ManageUsersResult(False, "password ne peut pas etre vide")

    existing = users_repo.load()
    if any(u.username == username for u in existing):
        return ManageUsersResult(False, f"l'utilisateur {username!r} existe deja (utiliser change-password)")

    users_repo.save(existing + (UserAccount(username=username, password_hash=hash_password(password)),))
    return ManageUsersResult(True, f"Utilisateur {username!r} cree.")


def remove_user(users_repo: UsersRepositoryPort, username: str) -> ManageUsersResult:
    existing = users_repo.load()
    remaining = tuple(u for u in existing if u.username != username)
    if len(remaining) == len(existing):
        return ManageUsersResult(False, f"utilisateur introuvable : {username!r}")

    users_repo.save(remaining)
    return ManageUsersResult(True, f"Utilisateur {username!r} retire.")


def change_password(users_repo: UsersRepositoryPort, username: str, new_password: str) -> ManageUsersResult:
    if not new_password:
        return ManageUsersResult(False, "password ne peut pas etre vide")

    existing = users_repo.load()
    if not any(u.username == username for u in existing):
        return ManageUsersResult(False, f"utilisateur introuvable : {username!r}")

    new_hash = hash_password(new_password)
    updated = tuple(
        UserAccount(username=u.username, password_hash=new_hash) if u.username == username else u
        for u in existing
    )
    users_repo.save(updated)
    return ManageUsersResult(True, f"Mot de passe change pour {username!r}.")
