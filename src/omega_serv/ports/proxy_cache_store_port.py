"""Contrat de stockage du cache de reponses proxiees (OMEGA-SERV_PLAN-
DETAILLE_REVERSE_PROXY.md §21 : Phase 8)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from omega_serv.domain.routing.proxy_cache import ProxyCacheEntry


@dataclass(frozen=True)
class ProxyCacheStats:
    entry_count: int
    total_size_bytes: int


class ProxyCacheStorePort(Protocol):
    def get(self, zone_key: str, cache_key: str) -> ProxyCacheEntry | None:
        ...

    def get_variants(self, zone_key: str, primary_key: str) -> tuple[ProxyCacheEntry, ...]:
        """Toutes les variantes connues (Phase 8, support multi-variantes
        `Vary`) dont la cle de stockage derive de `primary_key` (voir
        `domain/routing/proxy_cache.py::variant_cache_key`) - jamais
        l'entree exacte `primary_key` elle-meme (qui n'est jamais
        ecrite seule, uniquement suffixee par une empreinte de
        variante)."""
        ...

    def set(self, zone_key: str, cache_key: str, entry: ProxyCacheEntry) -> None:
        ...

    def delete(self, zone_key: str, cache_key: str) -> None:
        ...

    def clear(self, *, zone_key: str | None = None) -> int:
        """Purge totale (`zone_key=None`) ou ciblee par zone - retourne
        le nombre d'entrees retirees."""
        ...

    def stats(self, *, zone_key: str | None = None) -> ProxyCacheStats:
        ...
