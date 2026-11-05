"""Cas d'usage de la declaration anonyme d'utilisateur (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b).

- `declare` : interface ou CLI, au clic « Envoyer ». Le mode « une seule fois » n'enregistre rien
  si l'envoi echoue ; le mode « chaque jour » garde l'accord et le service reessaiera le lendemain.
- `withdraw` : « Ne plus me declarer ». Le retrait est envoye, puis tout est efface localement,
  meme si la reception est injoignable (l'entree disparaitra alors seule cote reception).
- `send_scheduled` : l'envoi quotidien, fait par le service, jamais plus d'une fois par 24 h.
- `declaration_status` : ce qu'affiche l'ecran (et `declaration status`)."""
from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from omega_serv.domain.declaration.model import (
    MODE_DAILY,
    MODE_ONCE,
    Declaration,
    build_payload,
    build_withdrawal,
    daily_send_due,
    declaration_errors,
    do_not_track,
)
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.declaration_port import (
    DeclarationSenderPort,
    DeclarationStorePort,
    SendOutcome,
    ServiceSendLog,
    StoredDeclaration,
)


def new_key() -> str:
    """128 bits tires au hasard (module secrets) : ne derive de rien (ni MAC, ni nom de machine)."""
    return secrets.token_hex(16)


@dataclass(frozen=True)
class DeclareResult:
    ok: bool
    recorded: bool
    """L'accord est garde localement (toujours vrai si ok ; vrai aussi en mode quotidien en echec)."""
    reason: str = ""


def preview_payload(
    store: DeclarationStorePort, version: str, mode: str, continent: str, country: str,
) -> dict[str, str]:
    """Message exact affiche avant l'envoi. Cle encore inexistante : sa forme seulement."""
    existing = store.load()
    key = existing.declaration.key if existing is not None else "0" * 32
    return build_payload(Declaration(key, mode, continent, country), version)


def declare(
    store: DeclarationStorePort, sender: DeclarationSenderPort, clock: ClockPort, version: str,
    mode: str, continent: str = "", country: str = "", key_factory: Callable[[], str] = new_key,
) -> DeclareResult:
    existing = store.load()
    key = existing.declaration.key if existing is not None else key_factory()
    declaration = Declaration(key, mode, continent, country)
    errors = declaration_errors(declaration)
    if errors:
        raise ValueError(", ".join(errors))
    now = clock.now()
    outcome = sender.send(dict(build_payload(declaration, version)))
    declared_at = existing.declared_at if existing is not None else now
    if outcome.ok:
        store.save(StoredDeclaration(declaration, declared_at, last_attempt=now, last_success=now))
        return DeclareResult(ok=True, recorded=True)
    if mode == MODE_DAILY:
        last_success = existing.last_success if existing is not None else None
        store.save(StoredDeclaration(declaration, declared_at, last_attempt=now, last_success=last_success,
                                     last_error=outcome.reason))
        return DeclareResult(ok=False, recorded=True, reason=outcome.reason)
    return DeclareResult(ok=False, recorded=False, reason=outcome.reason)


@dataclass(frozen=True)
class WithdrawResult:
    was_declared: bool
    reception_reached: bool


def withdraw(store: DeclarationStorePort, sender: DeclarationSenderPort) -> WithdrawResult:
    existing = store.load()
    if existing is None:
        store.delete()  # un journal d'envois orphelin, s'il en reste un
        return WithdrawResult(was_declared=False, reception_reached=False)
    outcome = sender.send(build_withdrawal(existing.declaration.key))
    store.delete()
    return WithdrawResult(was_declared=True, reception_reached=outcome.ok)


def send_scheduled(
    store: DeclarationStorePort, sender: DeclarationSenderPort, clock: ClockPort, version: str,
    environ: Mapping[str, str],
) -> SendOutcome | None:
    """None si rien n'est a envoyer (pas d'accord, mode « une seule fois », DO_NOT_TRACK, ou
    dernier essai de moins de 24 h - qu'il vienne de l'interface ou du service)."""
    stored = store.load()
    log = store.load_service_log()
    attempts = [t for t in (log.last_attempt, stored.last_attempt if stored else None) if t is not None]
    now = clock.now()
    if not daily_send_due(stored.declaration if stored else None, max(attempts) if attempts else None, now,
                          do_not_track_set=do_not_track(environ)):
        return None
    assert stored is not None
    outcome = sender.send(dict(build_payload(stored.declaration, version)))
    store.save_service_log(ServiceSendLog(
        last_attempt=now,
        last_success=now if outcome.ok else log.last_success,
        last_error="" if outcome.ok else outcome.reason,
    ))
    return outcome


@dataclass(frozen=True)
class DeclarationStatus:
    declaration: Declaration | None
    declared_at: datetime | None
    last_success: datetime | None
    last_error: str
    """Erreur du dernier essai (le plus recent, interface ou service) ; vide s'il a reussi."""
    do_not_track: bool


def declaration_status(store: DeclarationStorePort, environ: Mapping[str, str]) -> DeclarationStatus:
    stored = store.load()
    if stored is None:
        return DeclarationStatus(None, None, None, "", do_not_track(environ))
    log = store.load_service_log()
    successes = [t for t in (stored.last_success, log.last_success) if t is not None]
    tries = [(t, error) for t, error in ((stored.last_attempt, stored.last_error), (log.last_attempt, log.last_error))
             if t is not None]
    last_error = max(tries, key=lambda item: item[0])[1] if tries else ""
    return DeclarationStatus(
        stored.declaration, stored.declared_at, max(successes) if successes else None, last_error,
        do_not_track(environ),
    )


__all__ = [
    "MODE_DAILY", "MODE_ONCE", "DeclarationStatus", "DeclareResult", "WithdrawResult",
    "declaration_status", "declare", "new_key", "preview_payload", "send_scheduled", "withdraw",
]
