"""Authentification de l'administration web, dans le processus d'administration (tableau de bord web, lot 3 ;
OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §3, §3.1, §5.1 ; decisions de l'auteur du 2026-11-16).

- connexion : identifiant + mot de passe (scrypt, temps constant meme pour un compte inconnu) + code TOTP si le compte
  l'a active (ou un code de secours, rayé apres usage) ; un seul message d'echec, qui ne dit jamais quoi est faux ;
- tentatives : 5 echecs en 10 min, par adresse OU par compte, bloquent la connexion pendant une attente qui double a
  chaque echec de plus (1 min a 1 h) ; tout est ecrit dans le journal d'audit ;
- sessions en memoire du processus (un redemarrage ferme tout) : 8 h au plus, 30 min d'inactivite ; jeton aleatoire
  de 256 bits dans un cookie HttpOnly, SameSite=Strict (Secure en TLS) ; jeton CSRF par session ;
- chaque session garde l'empreinte du compte a la connexion (mot de passe, TOTP, role) : un changement fait dans le
  TUI ou la CLI, ou la suppression du compte, ferme aussitot ses sessions ;
- deux modes : Tableau de bord (consulter) et Administration (agir, role `administration` seulement) ; passer en
  Administration redemande mot de passe et code si la derniere saisie a plus de 15 min."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from typing import Literal

from omega_serv.application.admin_web.manage_accounts import normalize_backup_code
from omega_serv.domain.admin_web import totp
from omega_serv.domain.admin_web.accounts import BACKUP_CODES, AdminAccount
from omega_serv.domain.security.auth.password_hashing import hash_password, verify_password

Mode = Literal["tableau", "administration"]
MODES: tuple[Mode, ...] = ("tableau", "administration")
SESSION_MAX_SECONDS = 8 * 3600
SESSION_IDLE_SECONDS = 30 * 60
REAUTH_SECONDS = 15 * 60
FAILURE_WINDOW_SECONDS = 10 * 60
FAILURES_BEFORE_LOCK = 5
LOCK_MIN_SECONDS = 60
LOCK_MAX_SECONDS = 3600
MAX_SESSIONS = 100


@cache
def _dummy_hash() -> str:
    """Verifie quand le compte n'existe pas : meme duree de reponse, l'existence d'un compte ne se devine pas.
    Calcule au premier besoin, plus a l'import (0,3 s et 16 Mio de scrypt dans chaque processus, 2026-11-18)."""
    return hash_password("omega-serv-compte-inconnu")

LoginError = Literal["invalid", "locked", "totp_setup_required"]


def account_fingerprint(account: AdminAccount) -> str:
    material = f"{account.password_hash}\0{account.totp_secret}\0{account.role}".encode()
    return hashlib.sha256(material).hexdigest()


@dataclass
class Session:
    token: str
    username: str
    fingerprint: str
    csrf: str
    mode: Mode
    created: float
    last_seen: float
    last_auth: float
    notice: str = ""
    """Resultat de la derniere action, affiche une fois en haut de la page Administration (lot 5)."""
    notice_ok: bool = True
    pending: dict[str, str] | None = None
    """Action demandee pendant qu'une nouvelle saisie etait necessaire : proposee a la confirmation juste apres."""
    ip: str = ""
    """Adresse de connexion (sessions ouvertes, etude modules, module 5)."""

    @property
    def public_id(self) -> str:
        """Identifiant montre et utilise pour fermer une session : derive du jeton, jamais le jeton (12 caracteres)."""
        return hashlib.sha256(self.token.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class LoginResult:
    session: Session | None
    error: LoginError | None = None
    retry_after: int = 0


@dataclass
class _Failures:
    times: list[float] = field(default_factory=list)
    locked_until: float = 0.0
    streak: int = 0


def _account_key(username: str, ip: str) -> str:
    """Scan de securite n° 2 (2026-11-20, F28) : echecs comptes par couple compte + adresse. Un compteur par compte
    seul laissait n'importe quelle adresse permise bloquer l'administrateur legitime (bon mot de passe et bon TOTP
    refuses). Le verrou par adresse reste en plus."""
    return f"compte:{username}:ip:{ip}"


class AdminAuth:
    def __init__(
        self,
        accounts: Callable[[], tuple[AdminAccount, ...]],
        clock: Callable[[], float],
        audit: Callable[[str], None],
        *,
        local_only: bool,
        used_backup_codes: Callable[[], set[str]],
        mark_backup_code_used: Callable[[str], None],
        token: Callable[[], str] = lambda: secrets.token_urlsafe(32),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._accounts = accounts
        self._clock = clock
        self._audit = audit
        self.local_only = local_only
        """Relu a chaque rechargement (lot 5) : l'objet, et donc les sessions ouvertes, survit au rechargement."""
        self._used_backup_codes = used_backup_codes
        self._mark_backup_code_used = mark_backup_code_used
        self._token = token
        self._sleep = sleep
        self._sessions: dict[str, Session] = {}
        self._failures: dict[str, _Failures] = {}
        self._last_totp_step: dict[str, int] = {}

    # ------------------------------------------------------------------ tentatives
    def _locked(self, key: str, now: float) -> int:
        record = self._failures.get(key)
        return max(0, int(record.locked_until - now + 0.999)) if record is not None else 0

    def _fail(self, key: str, now: float) -> None:
        record = self._failures.setdefault(key, _Failures())
        record.times = [t for t in record.times if now - t < FAILURE_WINDOW_SECONDS] + [now]
        if len(record.times) >= FAILURES_BEFORE_LOCK:
            record.streak += 1
            record.locked_until = now + min(LOCK_MAX_SECONDS, LOCK_MIN_SECONDS * 2 ** (record.streak - 1))
        if len(self._failures) > 10_000:  # jamais une memoire sans borne face a un balayage d'adresses
            for stale in [k for k, r in self._failures.items() if r.locked_until < now and not r.times][:5000]:
                del self._failures[stale]

    # ------------------------------------------------------------------ facteurs
    def _second_factor_ok(self, account: AdminAccount, code: str, now: float) -> bool:
        if not account.totp_enabled:
            return True
        step = totp.verify(account.totp_secret, code, now, self._last_totp_step.get(account.username))
        if step is not None:
            self._last_totp_step[account.username] = step
            return True
        return self._use_backup_code(account, code)

    def _use_backup_code(self, account: AdminAccount, code: str) -> bool:
        candidate = normalize_backup_code(code)
        if len(candidate) != 9:
            return False
        used = self._used_backup_codes()
        for stored in account.backup_code_hashes:
            if stored not in used and verify_password(candidate, stored):
                self._mark_backup_code_used(stored)
                self._audit(f"code de secours utilise compte={account.username}")
                return True
        return False

    def _check_credentials(self, username: str, password: str, code: str, now: float) -> AdminAccount | None:
        account = next((a for a in self._accounts() if a.username == username), None)
        started = time.monotonic()
        password_ok = verify_password(password, account.password_hash if account else _dummy_hash())
        if account is None or not password_ok:
            # Scan de securite n° 2 (2026-11-20, F25) : avec le bon mot de passe et un code de forme « secours »,
            # chaque code restant coute un scrypt de plus - le temps de reponse disait si le mot de passe etait
            # juste. Meme attente ici (sans calcul : rien a gagner en CPU pour un attaquant), duree d'un scrypt
            # mesuree a l'instant multipliee par le nombre de codes qui auraient ete essayes.
            if len(normalize_backup_code(code)) == 9:
                self._sleep((time.monotonic() - started) * self._backup_attempts(account))
            return None
        return account if self._second_factor_ok(account, code, now) else None

    def _backup_attempts(self, account: AdminAccount | None) -> int:
        if account is None or not account.totp_enabled:
            return BACKUP_CODES  # compte inconnu ou sans TOTP : comme un compte neuf, jamais un indice d'existence
        used = self._used_backup_codes()
        return sum(1 for stored in account.backup_code_hashes if stored not in used)

    # ------------------------------------------------------------------ connexion
    def login(self, ip: str, username: str, password: str, code: str, mode: str) -> LoginResult:
        now = self._clock()
        wait = max(self._locked(f"ip:{ip}", now), self._locked(_account_key(username, ip), now))
        if wait:
            self._audit(f"connexion refusee (attente {wait} s) compte={username!r} ip={ip}")
            return LoginResult(None, "locked", wait)
        account = self._check_credentials(username, password, code, now)
        if account is None:
            self._fail(f"ip:{ip}", now)
            self._fail(_account_key(username, ip), now)
            self._audit(f"echec de connexion compte={username!r} ip={ip}")
            return LoginResult(None, "invalid")
        if account.can_administer and not account.totp_enabled and not self.local_only:
            self._audit(f"connexion refusee (TOTP obligatoire hors de la machine) compte={username} ip={ip}")
            return LoginResult(None, "totp_setup_required")
        for key in (f"ip:{ip}", _account_key(username, ip)):
            self._failures.pop(key, None)
        chosen: Mode = "administration" if mode == "administration" and account.can_administer else "tableau"
        self._expire(now)
        if len(self._sessions) >= MAX_SESSIONS:
            oldest = min(self._sessions.values(), key=lambda s: s.last_seen)
            del self._sessions[oldest.token]
        session = Session(self._token(), account.username, account_fingerprint(account), self._token(), chosen,
                          now, now, now)
        session.ip = ip
        self._sessions[session.token] = session
        self._audit(f"connexion compte={account.username} role={account.role} mode={chosen} ip={ip}")
        return LoginResult(session)

    def _expire(self, now: float) -> None:
        for token in [t for t, s in self._sessions.items()
                      if now - s.created > SESSION_MAX_SECONDS or now - s.last_seen > SESSION_IDLE_SECONDS]:
            del self._sessions[token]

    def session(self, token: str | None) -> Session | None:
        """Session valide pour ce jeton (et son compte inchange), sinon None ; prolonge l'inactivite."""
        if not token:
            return None
        now = self._clock()
        self._expire(now)
        session = self._sessions.get(token)
        if session is None:
            return None
        account = self.account_of(session)
        if account is None or account_fingerprint(account) != session.fingerprint:
            del self._sessions[token]
            self._audit(f"session fermee (compte modifie ou supprime) compte={session.username}")
            return None
        if session.mode == "administration" and not account.can_administer:
            session.mode = "tableau"
        session.last_seen = now
        return session

    def open_sessions(self) -> list[Session]:
        """Sessions encore valides, la plus recente d'abord (etude modules, module 5)."""
        self._expire(self._clock())
        return sorted(self._sessions.values(), key=lambda s: s.last_seen, reverse=True)

    def close_session(self, public_id: str, by: str, ip: str) -> bool:
        """Ferme la session `public_id` ; `by` : qui la ferme (compte ou « TUI »), note dans l'audit."""
        target = next((s for s in self._sessions.values() if s.public_id == public_id), None)
        if target is None:
            return False
        del self._sessions[target.token]
        self._audit(f"session fermee par {by} compte={target.username} session={public_id} ip={ip}")
        return True

    def account_of(self, session: Session) -> AdminAccount | None:
        return next((a for a in self._accounts() if a.username == session.username), None)

    def audit(self, message: str) -> None:
        self._audit(message)

    def csrf_ok(self, session: Session, token: str) -> bool:
        return hmac.compare_digest(session.csrf, token)

    def logout(self, session: Session, ip: str) -> None:
        self._sessions.pop(session.token, None)
        self._audit(f"deconnexion compte={session.username} ip={ip}")

    # ------------------------------------------------------------------ modes
    def needs_reauth(self, session: Session) -> bool:
        return self._clock() - session.last_auth > REAUTH_SECONDS

    def switch_mode(self, session: Session, mode: str, ip: str) -> Literal["ok", "reauth", "refused"]:
        account = self.account_of(session)
        if mode not in MODES or account is None:
            return "refused"
        if mode == "administration":
            if not account.can_administer:
                self._audit(f"mode administration refuse (role lecture) compte={session.username} ip={ip}")
                return "refused"
            if self.needs_reauth(session):
                return "reauth"
        session.mode = mode
        self._audit(f"mode {mode} compte={session.username} ip={ip}")
        return "ok"

    def reauthenticate(self, session: Session, password: str, code: str, ip: str) -> LoginResult:
        now = self._clock()
        wait = max(self._locked(f"ip:{ip}", now), self._locked(_account_key(session.username, ip), now))
        if wait:
            return LoginResult(None, "locked", wait)
        account = self._check_credentials(session.username, password, code, now)
        if account is None:
            self._fail(f"ip:{ip}", now)
            self._fail(_account_key(session.username, ip), now)
            self._audit(f"echec de nouvelle saisie compte={session.username} ip={ip}")
            return LoginResult(None, "invalid")
        session.last_auth = now
        session.fingerprint = account_fingerprint(account)
        if account.can_administer:
            session.mode = "administration"
        self._audit(f"nouvelle saisie, mode administration compte={session.username} ip={ip}")
        return LoginResult(session)
