"""Instance maitre et instances suivies (tableau de bord web, lot 6 ; OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md
§7 et §9.2 ; decisions de l'auteur du 2026-11-16, Q9 a Q11).

Cote instance suivie : un seul maitre accepte (Q11), avec des droits fixes chez elle (`lecture` ou `administration`) ;
on ne garde que le hache scrypt de son jeton. Accepter un nouveau maitre remplace l'ancien.

Cote maitre : les instances suivies (adresse, port, jeton en clair car il doit l'envoyer, empreinte du certificat
epinglee) et les sondes HTTP des backends qui ne sont pas omega-serv (§7.5).

Appairage par code (§7.3, chemin 2) : code de 8 caracteres sans lettres ambigues (environ 40 bits), fenetre de
10 minutes, 3 essais faux la ferment. La cle du HMAC est tiree du code par scrypt, salee par les deux nombres
aleatoires de l'echange : une preuve captee ne permet pas d'essayer les codes hors ligne en quelques minutes. Chaque
preuve couvre l'empreinte du certificat telle que le maitre la voit : un intermediaire TLS est detecte."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

Rights = Literal["lecture", "administration"]
RIGHTS: tuple[Rights, ...] = ("lecture", "administration")

PAIRING_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
"""Sans I, L, O, 0 ni 1 : rien a confondre en recopiant le code."""
PAIRING_CODE_LENGTH = 8
PAIRING_WINDOW_SECONDS = 600
PAIRING_MAX_ATTEMPTS = 3
PAIRING_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
"""Environ 16 Mo et quelques dizaines de millisecondes par essai : negligeable pour 3 essais, ruineux pour 2^40."""
NONCE_HEX_LENGTH = 64

_INSTANCE_ID = re.compile(r"^[0-9a-f]{12}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{64}$")
_MASTER_ID = re.compile(r"^[0-9a-f]{32}$")


# ---------------------------------------------------------------------------------------------- cote instance suivie
@dataclass(frozen=True)
class AcceptedMaster:
    master_id: str
    master_name: str
    token_hash: str
    rights: Rights
    since: str
    """Date ISO 8601 (UTC) de l'acceptation."""
    last_call: str = ""
    """Dernier appel recu (ISO 8601), ecrit par le processus d'administration au plus une fois par minute."""

    @property
    def can_administer(self) -> bool:
        return self.rights == "administration"

    def to_dict(self) -> dict[str, Any]:
        return {"master_id": self.master_id, "master_name": self.master_name, "token_hash": self.token_hash,
                "rights": self.rights, "since": self.since, "last_call": self.last_call}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcceptedMaster:
        rights = data["rights"]
        if rights not in RIGHTS:
            raise ValueError(f"droits inconnus : {rights!r}")
        return cls(str(data["master_id"]), str(data["master_name"]), str(data["token_hash"]), rights,
                   str(data["since"]), str(data.get("last_call", "")))


@dataclass(frozen=True)
class PairingWindow:
    code: str
    """Code normalise (8 caracteres, sans tiret). Garde en clair : il sert de cle, et ne vit que 10 minutes."""
    rights: Rights
    expires_at: float
    attempts: int = 0

    def open_at(self, now: float) -> bool:
        return now < self.expires_at and self.attempts < PAIRING_MAX_ATTEMPTS

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "rights": self.rights, "expires_at": self.expires_at, "attempts": self.attempts}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PairingWindow:
        rights = data["rights"]
        if rights not in RIGHTS:
            raise ValueError(f"droits inconnus : {rights!r}")
        return cls(str(data["code"]), rights, float(data["expires_at"]), int(data.get("attempts", 0)))


def new_pairing_code(randbelow: Callable[[int], int]) -> str:
    return "".join(PAIRING_ALPHABET[randbelow(len(PAIRING_ALPHABET))] for _ in range(PAIRING_CODE_LENGTH))


def normalize_pairing_code(text: str) -> str:
    """Majuscules, sans tiret ni espace ; chaine vide si ce n'est pas un code possible."""
    code = re.sub(r"[\s-]", "", text).upper()
    if len(code) != PAIRING_CODE_LENGTH or any(char not in PAIRING_ALPHABET for char in code):
        return ""
    return code


def display_pairing_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


# ---------------------------------------------------------------------------------------------- preuves d'appairage
def valid_nonce(text: object) -> bool:
    return isinstance(text, str) and bool(_NONCE.match(text))


def valid_master_id(text: object) -> bool:
    return isinstance(text, str) and bool(_MASTER_ID.match(text))


def valid_fingerprint(text: object) -> bool:
    """Empreinte SHA-256 du certificat (64 caracteres hexadecimaux), ou vide pour HTTP en boucle locale."""
    return isinstance(text, str) and (text == "" or bool(_FINGERPRINT.match(text)))


def pairing_key(code: str, nonce_instance: str, nonce_master: str) -> bytes:
    return hashlib.scrypt(code.encode("ascii"), salt=bytes.fromhex(nonce_instance) + bytes.fromhex(nonce_master),
                          dklen=32, **PAIRING_SCRYPT)


def _proof(key: bytes, *parts: str) -> str:
    return hmac.new(key, "\0".join(parts).encode("utf-8"), hashlib.sha256).hexdigest()


def master_proof(key: bytes, nonce_instance: str, nonce_master: str, fingerprint: str, master_id: str) -> str:
    return _proof(key, "omega-serv/appairage/maitre/1", nonce_instance, nonce_master, fingerprint, master_id)


def instance_proof(key: bytes, nonce_instance: str, nonce_master: str, fingerprint: str, token: str) -> str:
    return _proof(key, "omega-serv/appairage/instance/1", nonce_instance, nonce_master, fingerprint, token)


def proofs_equal(first: str, second: str) -> bool:
    return hmac.compare_digest(first.encode(), second.encode())


def format_fingerprint(fingerprint: str) -> str:
    """AB:CD:... comme les navigateurs l'affichent ; « HTTP (boucle locale) » est dit par l'appelant."""
    return ":".join(fingerprint[i:i + 2] for i in range(0, len(fingerprint), 2)).upper()


# ---------------------------------------------------------------------------------------------- cote maitre
Kind = Literal["omega-serv", "sonde"]


@dataclass(frozen=True)
class MasterIdentity:
    master_id: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"master_id": self.master_id, "name": self.name}


@dataclass(frozen=True)
class FollowedInstance:
    instance_id: str
    name: str
    kind: Kind
    address: str = ""
    port: int = 0
    token: str = ""
    fingerprint: str = ""
    """Vide : HTTP, admis seulement en boucle locale."""
    url: str = ""
    """Sonde HTTP seulement (§7.5)."""
    added: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"instance_id": self.instance_id, "name": self.name, "kind": self.kind, "address": self.address,
                "port": self.port, "token": self.token, "fingerprint": self.fingerprint, "url": self.url,
                "added": self.added}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FollowedInstance:
        kind = data["kind"]
        if kind not in ("omega-serv", "sonde") or not valid_instance_id(data["instance_id"]):
            raise ValueError("instance suivie invalide")
        return cls(str(data["instance_id"]), str(data["name"]), kind, str(data.get("address", "")),
                   int(data.get("port", 0)), str(data.get("token", "")), str(data.get("fingerprint", "")),
                   str(data.get("url", "")), str(data.get("added", "")))

    @property
    def target(self) -> str:
        if self.kind == "sonde":
            return self.url
        host = f"[{self.address}]" if ":" in self.address else self.address
        return f"{'https' if self.fingerprint else 'http'}://{host}:{self.port}/"


@dataclass(frozen=True)
class Fleet:
    instances: tuple[FollowedInstance, ...] = field(default_factory=tuple)

    def find(self, instance_id: str) -> FollowedInstance | None:
        return next((item for item in self.instances if item.instance_id == instance_id), None)


def valid_instance_id(text: object) -> bool:
    return isinstance(text, str) and bool(_INSTANCE_ID.match(text))


def is_loopback_address(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return address == "localhost"


def local_admin_address(bind: str) -> str:
    """Adresse par laquelle une instance de CETTE machine joint l'administration d'une autre : la boucle locale si
    elle ecoute partout (0.0.0.0, ::) ou sur localhost, sinon son adresse d'ecoute."""
    if bind in ("", "localhost"):
        return "127.0.0.1"
    try:
        parsed = ipaddress.ip_address(bind)
    except ValueError:
        return bind
    if parsed.is_unspecified:
        return "::1" if parsed.version == 6 else "127.0.0.1"
    return bind


def check_instance_address(address: str, port: object) -> str:
    """Message d'erreur (non traduit ici : cle stable pour l'appelant), ou chaine vide."""
    try:
        ipaddress.ip_address(address)
    except ValueError:
        if address != "localhost":
            return "adresse"
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        return "port"
    return ""
