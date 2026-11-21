"""Echeances des certificats dans le processus d'administration (etude modules, module 3) : un releve au demarrage,
puis toutes les 12 h et a chaque rechargement ; jamais pendant une page. Lu par la vue Certificats et par les
alertes (module 2)."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from omega_serv.application.tls.certificate_inventory import CertificateLine

CHECK_SECONDS = 12 * 3600


class CertificateWatch:
    def __init__(self, check: Callable[[], list[CertificateLine]], *, clock: Callable[[], float] = time.time,
                 every: float = CHECK_SECONDS) -> None:
        self._check = check
        self._clock = clock
        self._every = every
        self.lines: list[CertificateLine] = []
        self.checked_at: float | None = None
        self._wake = asyncio.Event()

    def refresh_soon(self) -> None:
        """Rechargement : nouveau releve sans attendre les 12 h (chemins de certificat peut-etre changes)."""
        self._wake.set()

    async def refresh(self) -> None:
        try:
            self.lines = await asyncio.to_thread(self._check)
        except Exception:  # noqa: BLE001 - un releve impossible garde le precedent
            return
        self.checked_at = self._clock()

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await self.refresh()
            self._wake.clear()
            waits = [asyncio.ensure_future(stop.wait()), asyncio.ensure_future(self._wake.wait())]
            try:
                await asyncio.wait(waits, timeout=self._every, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for waiter in waits:
                    waiter.cancel()
