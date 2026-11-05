"""Contrats de la declaration anonyme d'utilisateur (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b).

Deux fichiers, deux ecrivains, jamais le meme fichier ecrit par deux comptes :
- la declaration (accord, cle, mode, continent, pays, envois faits par l'interface) : ecrite par
  l'interface ou la CLI, au nom de l'utilisateur ;
- le journal des envois quotidiens : ecrit par le service (`serve`), au nom de son compte dedie."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from omega_serv.domain.declaration.model import Declaration


@dataclass(frozen=True)
class SendOutcome:
    ok: bool
    reason: str = ""
    """Vide si ok ; sinon « unreachable » (reseau, DNS, delai depasse, certificat) ou « http-<code> »."""


@dataclass(frozen=True)
class StoredDeclaration:
    declaration: Declaration
    declared_at: datetime
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    last_error: str = ""


@dataclass(frozen=True)
class ServiceSendLog:
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    last_error: str = ""


class DeclarationSenderPort(Protocol):
    def send(self, payload: dict[str, object]) -> SendOutcome:
        """POST HTTPS vers la reception. Ne leve jamais : un echec est un SendOutcome."""
        ...


class DeclarationStorePort(Protocol):
    def load(self) -> StoredDeclaration | None:
        ...

    def save(self, stored: StoredDeclaration) -> None:
        ...

    def delete(self) -> None:
        """Efface la declaration et le journal des envois (retrait). Jamais d'erreur si absents."""
        ...

    def load_service_log(self) -> ServiceSendLog:
        ...

    def save_service_log(self, log: ServiceSendLog) -> None:
        ...
