"""Contrat de ralentissement borne (plan_active_defense_omega_serv.md,
Phase 4, "mode guerre") - jamais une attente bloquante dans la boucle
asyncio principale (voir "Risques et garde-fous" du plan)."""
from __future__ import annotations

from typing import Protocol


class DelaySchedulerPort(Protocol):
    async def wait(self, delay_seconds: float) -> None:
        ...
