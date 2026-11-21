# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Reglages de protection des mots de passe Basic (retour utilisateur 2026-11-21 : reglables dans le menu
Authentification) - cache des succes, limite des echecs avant hachage, file des verifications. Rangés dans
`options.auth.settings["password_protection"]` ; absents = valeurs par defaut ci-dessous (celles du 2026-11-20)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields

SETTINGS_KEY = "password_protection"


@dataclass(frozen=True)
class PasswordProtection:
    success_ttl_seconds: int = 300
    """Succes retenu, renouvele a chaque requete ; 0 = aucun cache (scrypt a chaque requete)."""
    success_max_age_seconds: int = 3600
    """Plafond absolu apres la vraie verification, puis scrypt a nouveau."""
    success_entries: int = 4096
    """Succes retenus au plus (le plus anciennement utilise est retire)."""
    failure_window_seconds: int = 300
    failures_per_ip: int = 10
    failures_per_user: int = 30
    pending_checks_max: int = 10
    """Verifications en cours ou en attente au plus ; au-dela, 503 sans hachage."""


BOUNDS: dict[str, tuple[int, int]] = {
    "success_ttl_seconds": (0, 3600),
    "success_max_age_seconds": (60, 86400),
    "success_entries": (0, 100000),
    "failure_window_seconds": (10, 86400),
    "failures_per_ip": (1, 10000),
    "failures_per_user": (1, 100000),
    "pending_checks_max": (2, 1000),
}
FIELD_NAMES = tuple(field.name for field in fields(PasswordProtection))


@dataclass(frozen=True)
class ProtectionProblem:
    """`kind` : "unknown" (cle inconnue), "integer" (pas un entier), "range" (hors bornes), "order" (plafond plus
    court que la duree renouvelee)."""
    kind: str
    name: str
    low: int = 0
    high: int = 0


def protection_problems(raw: object) -> list[ProtectionProblem]:
    if raw is None:
        return []
    if not isinstance(raw, Mapping):
        return [ProtectionProblem("integer", SETTINGS_KEY)]
    problems: list[ProtectionProblem] = []
    for name, value in raw.items():
        if name not in BOUNDS:
            problems.append(ProtectionProblem("unknown", str(name)))
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append(ProtectionProblem("integer", name))
            continue
        low, high = BOUNDS[name]
        if not low <= value <= high:
            problems.append(ProtectionProblem("range", name, low, high))
    if not problems:
        merged = parse_protection(raw)
        if merged.success_max_age_seconds < merged.success_ttl_seconds:
            problems.append(ProtectionProblem("order", "success_max_age_seconds"))
    return problems


def parse_protection(raw: object) -> PasswordProtection:
    """Valeurs valides prises, le reste par defaut (la configuration est validee avant le demarrage)."""
    if not isinstance(raw, Mapping):
        return PasswordProtection()
    values = {name: value for name, value in raw.items()
              if name in BOUNDS and isinstance(value, int) and not isinstance(value, bool)
              and BOUNDS[name][0] <= value <= BOUNDS[name][1]}
    return PasswordProtection(**values)


def protection_from_settings(settings: Mapping[str, object] | None) -> PasswordProtection:
    return parse_protection((settings or {}).get(SETTINGS_KEY))
