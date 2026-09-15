# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat d'horloge - permet de substituer le temps dans les tests
(rotation de logs, expiration de certificats, fenetres de rate-limit)
sans dependre de datetime.now() fige dans le code appelant."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime:
        ...
