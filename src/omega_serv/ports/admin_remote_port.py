"""Contrats du maitre de l'administration web (tableau de bord web, lot 6) : appels vers les instances suivies,
sondes HTTP, et fichiers des deux cotes (instance suivie : maitre accepte ; maitre : identite et instances)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from omega_serv.domain.admin_web.master import AcceptedMaster, Fleet, MasterIdentity, PairingWindow


@dataclass(frozen=True)
class RemoteReply:
    status: int
    """0 : aucune reponse HTTP (voir `error`)."""
    payload: object = None
    fingerprint: str = ""
    """Empreinte SHA-256 du certificat vu ; vide en HTTP."""
    error: str = ""
    """`connexion`, `delai`, `tls`, `empreinte`, `reponse`, ou vide."""


@dataclass(frozen=True)
class ProbeReply:
    status: int
    milliseconds: int
    error: str = ""


class RemoteClientPort(Protocol):
    async def call(self, address: str, port: int, *, use_tls: bool, fingerprint: str | None, method: str,
                   path: str, token: str = "", body: object = None, account: str = "") -> RemoteReply: ...

    async def probe(self, url: str) -> ProbeReply: ...


class MasterStorePort(Protocol):
    def load_master(self) -> AcceptedMaster | None: ...
    def save_master(self, master: AcceptedMaster | None) -> None: ...
    def load_pairing(self) -> PairingWindow | None: ...
    def save_pairing(self, window: PairingWindow | None) -> None: ...


class FleetStorePort(Protocol):
    def identity(self, new_id: Callable[[], str], default_name: str) -> MasterIdentity: ...
    def load(self) -> Fleet: ...
    def save(self, fleet: Fleet) -> None: ...
