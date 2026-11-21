"""Comptes de l'administration web, lot 3 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §3, §5.1 ; decisions de
l'auteur du 2026-11-16).

- crees, modifies et supprimes seulement par le TUI ou la CLI, jamais par le web (un vol de session ne doit pas
  permettre de s'installer) ; aucun compte par defaut ;
- role `lecture` (Tableau de bord seulement) ou `administration` (Tableau de bord et Administration) ;
- mot de passe hache en scrypt (domain/security/auth/password_hashing.py, deja utilise par l'authentification du
  site) ;
- TOTP facultatif par compte, obligatoire pour un compte `administration` quand l'administration web sort de la
  boucle locale (choix b de l'auteur) ; 10 codes de secours a usage unique, gardes haches."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from omega_serv.core.i18n import _

Role = Literal["lecture", "administration"]
ROLES: tuple[Role, ...] = ("lecture", "administration")
MIN_PASSWORD_LENGTH = 12
BACKUP_CODES = 10
_USERNAME = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


@dataclass(frozen=True)
class AdminAccount:
    username: str
    password_hash: str
    role: Role = "lecture"
    totp_secret: str = ""
    """Secret base32 ; vide = TOTP inactif."""
    backup_code_hashes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def totp_enabled(self) -> bool:
        return bool(self.totp_secret)

    @property
    def can_administer(self) -> bool:
        return self.role == "administration"

    def to_dict(self) -> dict[str, Any]:
        return {"username": self.username, "password_hash": self.password_hash, "role": self.role,
                "totp_secret": self.totp_secret, "backup_code_hashes": list(self.backup_code_hashes)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdminAccount:
        role = data.get("role", "lecture")
        return cls(username=str(data["username"]), password_hash=str(data["password_hash"]),
                   role=role if role in ROLES else "lecture", totp_secret=str(data.get("totp_secret", "")),
                   backup_code_hashes=tuple(str(code) for code in data.get("backup_code_hashes", [])))


def username_error(username: str) -> str | None:
    if not _USERNAME.match(username):
        return _("Identifiant invalide : 1 à 32 caractères parmi lettres, chiffres, point, tiret et soulignement.")
    return None


def password_error(password: str, username: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return _("Mot de passe trop court : {count} caractères au moins.").format(count=MIN_PASSWORD_LENGTH)
    if password.strip().lower() == username.lower():
        return _("Le mot de passe ne peut pas être l'identifiant.")
    return None


def accounts_missing_totp(accounts: tuple[AdminAccount, ...]) -> list[str]:
    """Comptes `administration` sans TOTP : interdits hors boucle locale (choix b de l'auteur, 2026-11-16)."""
    return [account.username for account in accounts if account.can_administer and not account.totp_enabled]
