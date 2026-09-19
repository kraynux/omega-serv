"""Entites pures Auth (spec §15). Zones protegees et comptes
utilisateurs - jamais de mot de passe en clair transporte au-dela de
domain/security/auth/password_hashing.py, seulement des hashes deja
calcules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UserAccount:
    username: str
    password_hash: str


@dataclass(frozen=True)
class AuthZone:
    """Une zone protegee (spec §15.2, exemple zones.json). `allow_methods`
    vide signifie "aucune restriction de methode propre a la zone" - la
    liste blanche globale (security.allowed_methods) s'applique deja
    independamment, cette zone n'ajoute une restriction que si elle en
    definit une."""
    path_prefix: str
    realm: str
    allowed_users: tuple[str, ...]
    allow_methods: tuple[str, ...] = ()


AuthOutcome = Literal["not_protected", "allowed", "unauthenticated", "forbidden"]


@dataclass(frozen=True)
class AuthDecision:
    outcome: AuthOutcome
    realm: str | None = None
    username: str | None = None
