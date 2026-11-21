"""Instance suivie : accepter un maitre, appairage par code, appels du maitre (tableau de bord web, lot 6a ;
OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §7.1, §7.3, §7.4 et §9.2).

`MasterLinkManager` sert le TUI et la CLI (accepter directement, ouvrir une fenetre d'appairage, revoquer) ;
`MasterAccess` sert le processus d'administration (verifier le jeton du maitre a chaque appel, repondre a
l'appairage par code). Un seul maitre accepte (Q11) : en accepter un autre remplace l'ancien, revoque aussitot, avec
une ligne d'audit. Toute operation est ecrite dans le journal d'audit de l'instance."""
from __future__ import annotations

import asyncio
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from omega_serv.domain.admin_web.master import (
    PAIRING_WINDOW_SECONDS,
    RIGHTS,
    AcceptedMaster,
    PairingWindow,
    instance_proof,
    master_proof,
    new_pairing_code,
    pairing_key,
    proofs_equal,
    valid_master_id,
    valid_nonce,
)
from omega_serv.domain.security.auth.password_hashing import hash_password, verify_password
from omega_serv.ports.admin_remote_port import MasterStorePort

LAST_CALL_WRITE_SECONDS = 60.0
CHALLENGE_SECONDS = 60.0
MAX_CHALLENGES = 8
MAX_NAME_LENGTH = 80


def _iso(moment: float) -> str:
    return datetime.fromtimestamp(moment, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_name(text: object) -> str:
    """Nom affiche d'un maitre ou d'une instance : une ligne, sans caractere de controle, borne."""
    value = "".join(char for char in str(text) if char.isprintable()).strip()
    return value[:MAX_NAME_LENGTH]


@dataclass(frozen=True)
class AcceptOutcome:
    ok: bool
    error: str = ""
    """`exists` (un autre maitre est accepte, il faut --replace), `rights`, `master_id`, `write`."""
    token: str = ""
    replaced: str = ""
    """Nom du maitre remplace, s'il y en avait un."""


@dataclass(frozen=True)
class PairingOutcome:
    ok: bool
    error: str = ""
    code: str = ""
    expires_at: float = 0.0


class MasterLinkManager:
    """TUI et CLI de l'instance suivie."""

    def __init__(self, store: MasterStorePort, clock: Callable[[], float], audit: Callable[[str], None],
                 token: Callable[[], str] = lambda: secrets.token_urlsafe(32),
                 randbelow: Callable[[int], int] = secrets.randbelow) -> None:
        self._store = store
        self._clock = clock
        self._audit = audit
        self._token = token
        self._randbelow = randbelow

    def master(self) -> AcceptedMaster | None:
        return self._store.load_master()

    def pairing(self) -> PairingWindow | None:
        window = self._store.load_pairing()
        return window if window is not None and window.open_at(self._clock()) else None

    def accept(self, master_id: str, master_name: str, rights: str, *, replace_existing: bool,
               source: str) -> AcceptOutcome:
        """Chemin 1 (omega-connect, par SSH) : cree le jeton, n'en garde que le hache, le rend une seule fois."""
        if rights not in RIGHTS:
            return AcceptOutcome(False, "rights")
        if not valid_master_id(master_id):
            return AcceptOutcome(False, "master_id")
        current = self._store.load_master()
        if current is not None and current.master_id != master_id and not replace_existing:
            return AcceptOutcome(False, "exists", replaced=current.master_name)
        token = self._token()
        accepted = AcceptedMaster(master_id, clean_name(master_name) or master_id[:8], hash_password(token),
                                  rights, _iso(self._clock()))
        try:
            self._store.save_master(accepted)
        except OSError:
            return AcceptOutcome(False, "write")
        self._store.save_pairing(None)
        replaced = current.master_name if current is not None and current.master_id != master_id else ""
        self._audit(f"maitre accepte ({source}) nom={accepted.master_name!r} id={master_id} droits={rights}"
                    + (f" remplace={replaced!r}" if replaced else ""))
        return AcceptOutcome(True, token=token, replaced=replaced)

    def open_pairing(self, rights: str, *, replace_existing: bool) -> PairingOutcome:
        """Chemin 2 : fenetre de 10 minutes et code a usage unique. Ouvrir une nouvelle fenetre remplace l'ancienne."""
        if rights not in RIGHTS:
            return PairingOutcome(False, "rights")
        if self._store.load_master() is not None and not replace_existing:
            return PairingOutcome(False, "exists")
        window = PairingWindow(new_pairing_code(self._randbelow), rights,
                               self._clock() + PAIRING_WINDOW_SECONDS)
        try:
            self._store.save_pairing(window)
        except OSError:
            return PairingOutcome(False, "write")
        self._audit(f"fenetre d'appairage ouverte droits={rights} (10 min)")
        return PairingOutcome(True, code=window.code, expires_at=window.expires_at)

    def close_pairing(self) -> None:
        if self._store.load_pairing() is not None:
            self._store.save_pairing(None)
            self._audit("fenetre d'appairage fermee a la main")

    def revoke(self) -> str | None:
        """Nom du maitre revoque, ou None s'il n'y en avait pas."""
        current = self._store.load_master()
        if current is None:
            return None
        self._store.save_master(None)
        self._audit(f"maitre revoque nom={current.master_name!r} id={current.master_id}")
        return current.master_name


@dataclass(frozen=True)
class PairingReply:
    status: int
    payload: dict[str, object]


class MasterAccess:
    """Processus d'administration de l'instance suivie."""

    def __init__(self, store: MasterStorePort, clock: Callable[[], float], audit: Callable[[str], None],
                 fingerprint: Callable[[], str], instance_name: Callable[[], str],
                 token: Callable[[], str] = lambda: secrets.token_urlsafe(32),
                 nonce: Callable[[], str] = lambda: secrets.token_hex(32)) -> None:
        self._store = store
        self._clock = clock
        self._audit = audit
        self._fingerprint = fingerprint
        self._instance_name = instance_name
        self._token = token
        self._nonce = nonce
        self._verified: tuple[str, str] | None = None
        """(hache stocke, jeton) deja verifie par scrypt : les appels suivants comparent en temps constant."""
        self._last_written = 0.0
        self._challenges: dict[str, float] = {}

    # ------------------------------------------------------------------ appels du maitre
    def authenticate(self, authorization: str | None) -> AcceptedMaster | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[len("Bearer "):].strip()
        master = self._store.load_master()
        if master is None or not token or len(token) > 200:
            return None
        cached = self._verified
        if cached is not None and cached[0] == master.token_hash:
            ok = hmac.compare_digest(cached[1].encode(), token.encode())
        else:
            ok = verify_password(token, master.token_hash)
            if ok:
                self._verified = (master.token_hash, token)
        if not ok:
            return None
        now = self._clock()
        if now - self._last_written >= LAST_CALL_WRITE_SECONDS:
            self._last_written = now
            try:
                self._store.save_master(replace(master, last_call=_iso(now)))
            except OSError:
                pass  # le dernier appel n'est qu'une information
        return master

    # ------------------------------------------------------------------ appairage par code
    def challenge(self) -> PairingReply:
        now = self._clock()
        window = self._store.load_pairing()
        if window is None or not window.open_at(now):
            return PairingReply(403, {"error": "fenetre"})
        self._challenges = {key: until for key, until in self._challenges.items() if until > now}
        if len(self._challenges) >= MAX_CHALLENGES:
            return PairingReply(429, {"error": "occupe"})
        nonce = self._nonce()
        self._challenges[nonce] = now + CHALLENGE_SECONDS
        return PairingReply(200, {"nonce": nonce})

    async def prove(self, payload: object, peer_ip: str) -> PairingReply:
        if not isinstance(payload, dict):
            return PairingReply(400, {"error": "requete"})
        nonce_i, nonce_m = payload.get("nonce_instance"), payload.get("nonce_maitre")
        master_id, proof = payload.get("maitre_id"), payload.get("preuve")
        if not (valid_nonce(nonce_i) and valid_nonce(nonce_m) and valid_master_id(master_id)
                and isinstance(proof, str) and len(proof) == 64):
            return PairingReply(400, {"error": "requete"})
        assert isinstance(nonce_i, str) and isinstance(nonce_m, str) and isinstance(master_id, str)
        now = self._clock()
        window = self._store.load_pairing()
        if window is None or not window.open_at(now):
            return PairingReply(403, {"error": "fenetre"})
        if self._challenges.pop(nonce_i, 0.0) <= now:
            return PairingReply(400, {"error": "defi"})
        fingerprint = self._fingerprint()
        key = await asyncio.to_thread(pairing_key, window.code, nonce_i, nonce_m)
        if not proofs_equal(master_proof(key, nonce_i, nonce_m, fingerprint, master_id), proof):
            attempts = window.attempts + 1
            closed = attempts >= 3
            self._store.save_pairing(None if closed else replace(window, attempts=attempts))
            self._audit(f"appairage refuse (code faux ou certificat intercepte) ip={peer_ip} essai={attempts}"
                        + (" -> fenetre fermee" if closed else ""))
            return PairingReply(403, {"error": "preuve"})
        master_name = clean_name(payload.get("maitre_nom", "")) or master_id[:8]
        current = self._store.load_master()
        token = self._token()
        accepted = AcceptedMaster(master_id, master_name, hash_password(token), window.rights, _iso(now))
        self._store.save_master(accepted)
        self._store.save_pairing(None)
        self._verified = None
        replaced = current.master_name if current is not None and current.master_id != master_id else ""
        self._audit(f"maitre accepte (code) nom={master_name!r} id={master_id} droits={window.rights} ip={peer_ip}"
                    + (f" remplace={replaced!r}" if replaced else ""))
        return PairingReply(200, {"jeton": token, "droits": window.rights, "nom": self._instance_name(),
                                  "preuve": instance_proof(key, nonce_i, nonce_m, fingerprint, token)})
