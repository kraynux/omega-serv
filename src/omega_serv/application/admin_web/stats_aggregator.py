"""Statistiques de trafic dans le processus d'administration (etude modules, module 2 ; decisions de l'auteur du
2026-11-17 : sans pays, 5xx comptes dans la meme lecture du journal).

La sonde de l'Historique passe ici les lignes completes ajoutees au journal d'acces (fil de travail) ; la vue Trafic
lit les totaux (boucle principale) : un verrou protege le jour courant. Jour courant ecrit toutes les 5 minutes, au
changement de jour et a l'arret ; 31 jours gardes."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

from omega_serv.domain.admin_web.traffic_stats import KEEP_DAYS, StatsDay, StatsSummary, summarize
from omega_serv.ports.admin_stats_port import StatsStorePort

SAVE_SECONDS = 300.0
PERIODS = {"jour": 1, "7j": 7, "30j": 30}


class StatsAggregator:
    def __init__(self, store: StatsStorePort, *, clock: Callable[[], float] = time.time) -> None:
        self._store = store
        self._clock = clock
        self._lock = threading.Lock()
        today = self._day(clock())
        self._today = StatsDay.from_dict(store.load(today), today)
        self._saved_at = clock()
        self._past: dict[str, StatsDay] = {}
        """Jours passes deja relus (ils ne changent plus)."""
        self.errors_5xx = 0
        """Cumul depuis le demarrage (alertes : taux de 5xx sur 5 minutes, via l'Historique)."""

    @staticmethod
    def _day(stamp: float) -> str:
        return time.strftime("%Y-%m-%d", time.localtime(stamp))

    def feed(self, lines: list[bytes]) -> None:
        now = self._clock()
        hour = time.localtime(now).tm_hour
        with self._lock:
            if self._day(now) != self._today.day:
                self._save_locked()
                self._today = StatsDay(self._day(now))
                self._prune()
            for line in lines:
                code = self._today.add(line, hour)
                if code is not None and code >= 500:
                    self.errors_5xx += 1
            due = now - self._saved_at >= SAVE_SECONDS
        if due:
            self.save()

    def save(self) -> None:
        with self._lock:
            self._save_locked()

    def _save_locked(self) -> None:
        self._saved_at = self._clock()
        try:
            self._store.save(self._today.day, self._today.to_dict())
        except OSError:
            pass  # dossier non inscriptible : le jour reste en memoire

    def _prune(self) -> None:
        days = self._store.days()
        for day in days[:-KEEP_DAYS]:
            self._store.remove(day)
            self._past.pop(day, None)

    def summary(self, period: str) -> StatsSummary:
        count = PERIODS.get(period, 1)
        with self._lock:
            today = StatsDay.from_dict(self._today.to_dict(), self._today.day)
        wanted = [self._day(self._clock() - offset * 86400) for offset in range(1, count)]
        days = [today]
        for day in wanted:
            if day not in self._past:
                data = self._store.load(day)
                if data is None:
                    continue
                self._past[day] = StatsDay.from_dict(data, day)
            days.append(self._past[day])
        return summarize(days)
