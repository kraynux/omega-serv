"""Historique du tableau de bord web, lots 7 et 9 (plan §8, §9.5) : releve toutes les 10 s dans le processus
d'administration, que quelqu'un regarde ou non ; paliers de 10 s a 2 h (1 h a 30 jours) en memoire, fichier ecrit toutes les 5 min et a l'arret, relu au
demarrage (un rechargement ou un redemarrage ne perd que les dernieres minutes). Desactivable : `history: false` dans
l'option admin_web."""
from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import Any

from omega_serv.domain.admin_web.history import SHORT_STEP, Counters, HistoryRings, point_between
from omega_serv.ports.admin_history_port import HistoryProbePort, HistoryStorePort

SAVE_SECONDS = 300.0


class HistoryRecorder:
    def __init__(self, probe: HistoryProbePort, store: HistoryStorePort, *, clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic, step: float = SHORT_STEP) -> None:
        self._probe = probe
        self._store = store
        self._clock = clock
        self._monotonic = monotonic
        self._step = step
        try:
            saved = store.load()
        except OSError:
            saved = None
        self.rings = HistoryRings.from_dict(saved, clock())
        self._previous: Counters | None = None
        self._saved_at = monotonic()
        self.listener: Callable[[dict[str, float | None]], None] | None = None
        """Alertes locales (etude modules, module 1) : recoit chaque point, jamais d'exception remontee."""

    def record(self, counters: Counters) -> None:
        previous, self._previous = self._previous, counters
        if previous is None:
            return
        point = point_between(previous, counters)
        if point is not None:
            self.rings.add(point)
            if self.listener is not None:
                with contextlib.suppress(Exception):  # une alerte en defaut ne coupe jamais l'historique
                    self.listener(point)

    def save(self) -> None:
        try:
            self._store.save(self.rings.to_dict())
        except OSError:
            pass  # dossier non inscriptible : l'historique reste en memoire
        self._saved_at = self._monotonic()

    def series(self, range_name: str, mode: str = "avg") -> dict[str, Any] | None:
        found = self.rings.series(range_name, self._clock(), mode)
        if found is not None:
            try:
                found["capacites"] = self._probe.capacities()
            except Exception:  # noqa: BLE001 - sans tailles, les graphes gardent le pourcentage seul
                found["capacites"] = {}
        return found

    async def run(self, stop: asyncio.Event) -> None:
        try:
            while not stop.is_set():
                try:
                    self.record(await asyncio.to_thread(self._probe.read))
                except Exception:  # noqa: BLE001 - un releve impossible ne coupe jamais l'historique
                    self._previous = None
                if self._monotonic() - self._saved_at >= SAVE_SECONDS:
                    await asyncio.to_thread(self.save)
                try:
                    await asyncio.wait_for(stop.wait(), self._step)
                except TimeoutError:
                    pass
        finally:
            self.save()
