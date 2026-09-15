# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de stockage/compteur de rate limit (doc WAF, tableau
"Repartition Clean Architecture" : ports/rate_limit_port.py)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RateLimitCheckResult:
    allowed: bool
    retry_after_seconds: int | None


class RateLimitPort(Protocol):
    def check(self, key: str, requests: int, window_seconds: int) -> RateLimitCheckResult:
        ...

    def reset(self, key: str | None = None) -> None:
        """Reinitialise les compteurs - une cle precise, ou tout (menu
        CLI 16 : "Reinitialiser les compteurs de rate limit")."""
        ...
