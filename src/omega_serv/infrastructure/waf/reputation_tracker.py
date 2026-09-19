"""Compteur de recidive par IP (doc WAF §8) - etat en memoire, remis a
zero au redemarrage (meme decision que le rate limit, voir
rate_limit_store.py). Ne decide PAS lui-meme de l'escalade : ce module
ne fait que compter, domain/security/waf/reputation.py::evaluate_escalation
decide (pur), et application/security/evaluate_waf_request.py orchestre
les deux avec le blocklist_port.

Retour utilisateur (audit memoire, 2026-09-14) : pire que le rate
limiter - `count_hits_in_window` elaguait deja les timestamps perimes
de la LISTE par IP, mais reecrivait toujours `self._hits[ip]` meme
quand la liste resultante etait vide, ne supprimant jamais la CLE.
Comme le seul appelant reel (evaluate_waf_request.py) enchaine toujours
`record_hit(ip)` puis `count_hits_in_window(ip, ...)` pour la MEME ip
dans la foulee, le timestamp fraichement ajoute passe systematiquement
le filtre - la liste n'est donc en pratique JAMAIS vide a cet instant
precis, et le simple "supprimer si vide" ne suffit pas a corriger le
vrai probleme : une IP qui ne frappe qu'UNE SEULE FOIS (n'importe quel
scan Internet massif, tres courant) reste alors en memoire pour
toujours, meme apres expiration complete de sa fenetre de reputation.
Balayage periodique et amorti par TTL, meme principe que
rate_limit_store.py."""
from __future__ import annotations

from omega_serv.ports.clock_port import ClockPort

_DEFAULT_TTL_SECONDS = 3600.0
_SWEEP_INTERVAL_SECONDS = 60.0


class InMemoryReputationTracker:
    def __init__(self, clock: ClockPort, ttl_seconds: float = _DEFAULT_TTL_SECONDS):
        self._clock = clock
        self._hits: dict[str, list[float]] = {}
        self._ttl_seconds = ttl_seconds
        self._last_sweep = 0.0

    def record_hit(self, ip: str) -> None:
        now = self._clock.now().timestamp()
        self._sweep_stale_entries_if_due(now)
        self._hits.setdefault(ip, []).append(now)

    def count_hits_in_window(self, ip: str, window_seconds: int) -> int:
        now = self._clock.now().timestamp()
        cutoff = now - window_seconds
        timestamps = [t for t in self._hits.get(ip, []) if t >= cutoff]
        if timestamps:
            self._hits[ip] = timestamps
        else:
            self._hits.pop(ip, None)
        return len(timestamps)

    def reset(self, ip: str | None = None) -> None:
        if ip is None:
            self._hits.clear()
        else:
            self._hits.pop(ip, None)

    def _sweep_stale_entries_if_due(self, now: float) -> None:
        if now - self._last_sweep < _SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep = now
        cutoff = now - self._ttl_seconds
        stale_ips = [ip for ip, timestamps in self._hits.items() if not timestamps or max(timestamps) <= cutoff]
        for ip in stale_ips:
            del self._hits[ip]
