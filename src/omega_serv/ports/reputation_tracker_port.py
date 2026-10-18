"""Contrat de comptage de recidive par IP (doc WAF §8, "reputation_escalation").
Separe volontairement du blocklist_port : ce port ne fait que compter,
la decision d'escalade est domain/security/waf/reputation.py (pur)."""
from __future__ import annotations

from typing import Protocol


class ReputationTrackerPort(Protocol):
    # `key` (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.12) : compteur
    # separe par (IP, cle) - "global" = compteur commun historique, l'id
    # d'une keyword_list = son compteur de recidive propre. Defaut =
    # comportement anterieur pour tous les appelants existants.
    def record_hit(self, ip: str, key: str = "global") -> None:
        ...

    def count_hits_in_window(self, ip: str, window_seconds: int, key: str = "global") -> int:
        ...

    def reset(self, ip: str | None = None) -> None:
        ...
