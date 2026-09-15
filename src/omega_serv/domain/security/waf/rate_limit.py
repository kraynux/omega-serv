# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Algorithme token bucket (doc WAF §7 : "token bucket : recommande a
terme pour absorber les rafales controlees"). Fonction pure sur un
etat immuable - la persistance/le stockage par cle (IP, IP+zone) est
une responsabilite d'infrastructure/waf/rate_limit_store.py, jamais de
ce module."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenBucketState:
    tokens: float
    last_refill: float


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    new_state: TokenBucketState
    retry_after_seconds: float | None


def consume_token(
    state: TokenBucketState | None,
    now: float,
    capacity: int,
    window_seconds: int,
) -> RateLimitResult:
    """Un bucket de capacite `capacity` se remplit lineairement sur
    `window_seconds` (ex. 60 requetes/60s = 1 jeton/s). `state=None`
    signifie un bucket jamais vu, initialise plein (premiere requete
    d'une cle toujours autorisee)."""
    refill_rate = capacity / window_seconds if window_seconds > 0 else capacity

    if state is None:
        tokens = float(capacity)
        last_refill = now
    else:
        elapsed = max(0.0, now - state.last_refill)
        tokens = min(float(capacity), state.tokens + elapsed * refill_rate)
        last_refill = now

    if tokens >= 1.0:
        return RateLimitResult(
            allowed=True,
            new_state=TokenBucketState(tokens=tokens - 1.0, last_refill=last_refill),
            retry_after_seconds=None,
        )

    missing = 1.0 - tokens
    retry_after = missing / refill_rate if refill_rate > 0 else float(window_seconds)
    return RateLimitResult(
        allowed=False,
        new_state=TokenBucketState(tokens=tokens, last_refill=last_refill),
        retry_after_seconds=retry_after,
    )
