"""Gestion des comptes de l'administration web, partagee par le TUI et la CLI (tableau de bord web, lot 3).

Jamais appelee par le web (decision de l'auteur du 2026-11-16 : comptes, mots de passe et TOTP se reglent sur la
machine). Activation TOTP en deux temps : `new_totp_secret` tire un secret sans rien ecrire, `confirm_totp`
l'enregistre seulement si le code tape est juste (un secret mal scanne ne bloque jamais le compte) et rend les 10
codes de secours, montres une seule fois puis gardes haches."""
from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from omega_serv.core.i18n import _
from omega_serv.domain.admin_web import totp
from omega_serv.domain.admin_web.accounts import (
    BACKUP_CODES,
    ROLES,
    AdminAccount,
    password_error,
    username_error,
)
from omega_serv.domain.security.auth.password_hashing import hash_password
from omega_serv.ports.admin_accounts_port import AdminAccountsPort

_BACKUP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I/L : se recopie sans erreur


@dataclass(frozen=True)
class AccountResult:
    success: bool
    message: str
    backup_codes: tuple[str, ...] = ()


def new_backup_code(random_choice: Callable[[str], str] = secrets.choice) -> str:
    raw = "".join(random_choice(_BACKUP_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_backup_code(code: str) -> str:
    cleaned = code.strip().upper().replace(" ", "").replace("-", "")
    return f"{cleaned[:4]}-{cleaned[4:]}" if len(cleaned) == 8 else cleaned


def _find(accounts: tuple[AdminAccount, ...], username: str) -> AdminAccount | None:
    return next((a for a in accounts if a.username == username), None)


def _replace(store: AdminAccountsPort, accounts: tuple[AdminAccount, ...], updated: AdminAccount) -> None:
    store.save(tuple(updated if a.username == updated.username else a for a in accounts))


def add_account(store: AdminAccountsPort, username: str, password: str, role: str) -> AccountResult:
    error = username_error(username) or password_error(password, username)
    if error is None and role not in ROLES:
        error = _("Rôle inconnu : {role} (lecture ou administration).").format(role=role)
    accounts = store.load()
    if error is None and _find(accounts, username) is not None:
        error = _("Le compte {name!r} existe déjà.").format(name=username)
    if error is not None:
        return AccountResult(False, error)
    store.save((*accounts, AdminAccount(username, hash_password(password), role)))  # type: ignore[arg-type]
    return AccountResult(True, _("Compte {name!r} créé ({role}).").format(name=username, role=role))


def remove_account(store: AdminAccountsPort, username: str) -> AccountResult:
    accounts = store.load()
    if _find(accounts, username) is None:
        return AccountResult(False, _("Compte {name!r} introuvable.").format(name=username))
    store.save(tuple(a for a in accounts if a.username != username))
    return AccountResult(True, _("Compte {name!r} supprimé : ses sessions ouvertes sont fermées.").format(
        name=username))


def set_password(store: AdminAccountsPort, username: str, password: str) -> AccountResult:
    accounts = store.load()
    account = _find(accounts, username)
    if account is None:
        return AccountResult(False, _("Compte {name!r} introuvable.").format(name=username))
    error = password_error(password, username)
    if error is not None:
        return AccountResult(False, error)
    _replace(store, accounts, replace(account, password_hash=hash_password(password)))
    return AccountResult(True, _("Mot de passe de {name!r} changé : ses sessions ouvertes sont fermées.").format(
        name=username))


def set_role(store: AdminAccountsPort, username: str, role: str) -> AccountResult:
    accounts = store.load()
    account = _find(accounts, username)
    if account is None:
        return AccountResult(False, _("Compte {name!r} introuvable.").format(name=username))
    if role not in ROLES:
        return AccountResult(False, _("Rôle inconnu : {role} (lecture ou administration).").format(role=role))
    _replace(store, accounts, replace(account, role=role))
    return AccountResult(True, _("Rôle de {name!r} : {role}.").format(name=username, role=role))


def new_totp_secret(random_bytes: Callable[[int], bytes] = secrets.token_bytes) -> str:
    return totp.new_secret(random_bytes(totp.SECRET_BYTES))


def confirm_totp(store: AdminAccountsPort, username: str, secret: str, code: str,
                 now: Callable[[], float] = time.time) -> AccountResult:
    """Enregistre le secret si `code` est juste ; rend les codes de secours (a montrer une seule fois)."""
    accounts = store.load()
    account = _find(accounts, username)
    if account is None:
        return AccountResult(False, _("Compte {name!r} introuvable.").format(name=username))
    if totp.verify(secret, code, now(), None) is None:
        return AccountResult(False, _("Code incorrect : vérifiez l'heure du téléphone et recommencez avec le code "
                                      "affiché maintenant. Rien n'a été enregistré."))
    codes = tuple(new_backup_code() for _ in range(BACKUP_CODES))
    _replace(store, accounts, replace(account, totp_secret=secret,
                                      backup_code_hashes=tuple(hash_password(c) for c in codes)))
    return AccountResult(True, _("TOTP activé pour {name!r} : ses sessions ouvertes sont fermées.").format(
        name=username), codes)


LOW_BACKUP_CODES = 2
"""A partir de ce nombre de codes restants (ou moins), l'ecran Comptes previent."""


def remaining_backup_codes(account: AdminAccount, used: set[str]) -> int:
    """Codes de secours encore utilisables : les haches du compte qui ne sont pas dans la liste des codes utilises
    (tenue par le processus d'administration dans var/lib/admin/)."""
    return sum(1 for code_hash in account.backup_code_hashes if code_hash not in used)


def regenerate_backup_codes(store: AdminAccountsPort, username: str) -> AccountResult:
    """10 nouveaux codes ; les anciens ne marchent plus. Le secret TOTP du telephone ne change pas, ni les sessions
    ouvertes (l'empreinte de session ne porte que sur le mot de passe, le secret et le role)."""
    accounts = store.load()
    account = _find(accounts, username)
    if account is None:
        return AccountResult(False, _("Compte {name!r} introuvable.").format(name=username))
    if not account.totp_enabled:
        return AccountResult(False, _("TOTP n'est pas activé pour {name!r} : les codes de secours viennent avec "
                                      "l'activation de TOTP.").format(name=username))
    codes = tuple(new_backup_code() for _ in range(BACKUP_CODES))
    _replace(store, accounts, replace(account, backup_code_hashes=tuple(hash_password(c) for c in codes)))
    return AccountResult(True, _("Nouveaux codes de secours pour {name!r} : les anciens ne marchent plus.").format(
        name=username), codes)


def disable_totp(store: AdminAccountsPort, username: str) -> AccountResult:
    accounts = store.load()
    account = _find(accounts, username)
    if account is None:
        return AccountResult(False, _("Compte {name!r} introuvable.").format(name=username))
    _replace(store, accounts, replace(account, totp_secret="", backup_code_hashes=()))
    return AccountResult(True, _("TOTP désactivé pour {name!r}.").format(name=username))
