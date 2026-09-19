"""Escalade de reputation (doc WAF §8) : separe le score WAF d'une
requete individuelle du comportement recidiviste d'une IP dans le
temps. Fonction pure - le comptage effectif des hits par IP/fenetre est
une responsabilite d'infrastructure/waf/reputation_tracker.py (etat
mutable), pas de ce module."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReputationDecision:
    should_escalate: bool
    reason: str


def evaluate_escalation(hit_count_in_window: int, suspicious_threshold: int) -> ReputationDecision:
    """`hit_count_in_window` est le nombre de requetes ayant declenche
    au moins un finding WAF pour une IP donnee, dans la fenetre
    configuree (reputation.window_seconds) - calcule par l'appelant
    (le tracker d'infrastructure), pas ici."""
    if suspicious_threshold <= 0:
        return ReputationDecision(should_escalate=False, reason="seuil desactive (<= 0)")
    if hit_count_in_window >= suspicious_threshold:
        return ReputationDecision(
            should_escalate=True,
            reason=f"{hit_count_in_window} detections suspectes dans la fenetre (seuil {suspicious_threshold})",
        )
    return ReputationDecision(should_escalate=False, reason="sous le seuil")
