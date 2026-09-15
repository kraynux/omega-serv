# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Resolution de zone generique (decision transverse, voir
OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6) : alias, redirections, cache,
directory listing et (plus tard) auth/CSP/politiques de service WAF
matchent tous un chemin par prefixe d'URL. Un seul mecanisme partage
(plus-long-prefixe-gagne) plutot que chaque fonctionnalite reimplemente
sa propre logique de correspondance legerement differente."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Zone(Generic[T]):
    path_prefix: str
    data: T


def resolve_zone(path: str, zones: list[Zone[T]]) -> Zone[T] | None:
    """Retourne la zone dont le `path_prefix` correspond au chemin et
    est le plus long (la plus specifique gagne) - None si aucune zone
    ne correspond."""
    matches = [zone for zone in zones if path.startswith(zone.path_prefix)]
    if not matches:
        return None
    return max(matches, key=lambda zone: len(zone.path_prefix))
