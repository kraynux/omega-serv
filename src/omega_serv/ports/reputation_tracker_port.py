# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de comptage de recidive par IP (doc WAF §8, "reputation_escalation").
Separe volontairement du blocklist_port : ce port ne fait que compter,
la decision d'escalade est domain/security/waf/reputation.py (pur)."""
from __future__ import annotations

from typing import Protocol


class ReputationTrackerPort(Protocol):
    def record_hit(self, ip: str) -> None:
        ...

    def count_hits_in_window(self, ip: str, window_seconds: int) -> int:
        ...

    def reset(self, ip: str | None = None) -> None:
        ...
