# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation reelle de RateLimitPort : etat en memoire (doc WAF
§7 - "Utiliser JSON strict, SQLite ou une structure en memoire sans
persistance dans la premiere version" ; "un store memoire est souvent
preferable pour un rate limit local, la remise a zero apres redemarrage
est acceptable"). Utilise l'algorithme token bucket pur de
domain/security/waf/rate_limit.py.

Retour utilisateur (audit memoire, 2026-09-14) : `_buckets` recevait une
entree par IP source unique et n'etait jamais purge - ni TTL, ni
eviction periodique, `reset()` n'etant appele nulle part en production.
A l'echelle visee (WAF actif, trafic eleve, semaines/mois d'uptime sans
redemarrage), des millions d'IP uniques s'accumulaient indefiniment,
jamais liberees meme quand une IP ne revient plus - egalement un vecteur
de deni de service memoire supplementaire (un attaquant faisant varier
ses IP source accelere volontairement la croissance). Balayage
periodique et amorti (jamais a chaque appel - couterait aussi cher que
le probleme qu'il resout a tres haut debit) : un bucket dont le dernier
ravitaillement remonte a plus de `ttl_seconds` a deja necessairement
regagne sa capacite pleine (le token bucket se remplit lineairement sur
`window_seconds`, toujours tres inferieur au TTL par defaut) - le
supprimer ne change donc AUCUN comportement observable, une nouvelle
entree pour la meme cle demarrerait de toute facon a pleine capacite
(`consume_token(None, ...)`)."""
from __future__ import annotations

from omega_serv.domain.security.waf.rate_limit import TokenBucketState, consume_token
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.rate_limit_port import RateLimitCheckResult

_DEFAULT_TTL_SECONDS = 3600.0
_SWEEP_INTERVAL_SECONDS = 60.0


class InMemoryRateLimitStore:
    def __init__(self, clock: ClockPort, ttl_seconds: float = _DEFAULT_TTL_SECONDS):
        self._clock = clock
        self._buckets: dict[str, TokenBucketState] = {}
        self._ttl_seconds = ttl_seconds
        self._last_sweep = 0.0

    def check(self, key: str, requests: int, window_seconds: int) -> RateLimitCheckResult:
        now = self._clock.now().timestamp()
        self._sweep_stale_entries_if_due(now)
        state = self._buckets.get(key)
        result = consume_token(state, now, capacity=requests, window_seconds=window_seconds)
        self._buckets[key] = result.new_state
        retry_after = None if result.retry_after_seconds is None else int(result.retry_after_seconds) + 1
        return RateLimitCheckResult(allowed=result.allowed, retry_after_seconds=retry_after)

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._buckets.clear()
        else:
            self._buckets.pop(key, None)

    def _sweep_stale_entries_if_due(self, now: float) -> None:
        if now - self._last_sweep < _SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep = now
        stale_keys = [key for key, state in self._buckets.items() if now - state.last_refill > self._ttl_seconds]
        for key in stale_keys:
            del self._buckets[key]
