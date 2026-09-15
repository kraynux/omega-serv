# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implemente ports.delay_scheduler_port.DelaySchedulerPort
(plan_active_defense_omega_serv.md, Phase 4, "mode guerre") - un simple
`asyncio.sleep`, jamais une attente bloquante : ceder le controle a la
boucle d'evenements pendant le delai n'empeche jamais le traitement des
autres connexions (voir "Risques et garde-fous" du plan)."""
from __future__ import annotations

import asyncio


class AsyncioDelayScheduler:
    async def wait(self, delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)
