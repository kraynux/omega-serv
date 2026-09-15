# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation reelle de ports.clock_port.ClockPort - premiere
consommatrice : le module WAF (blocklist/rate-limit/reputation), qui a
besoin de substituer le temps dans les tests sans dependre de
datetime.now() fige dans le code appelant."""
from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
