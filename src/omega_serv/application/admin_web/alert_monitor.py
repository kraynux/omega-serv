"""Surveillance des alertes locales dans le processus d'administration (etude modules, module 1 ; decisions de
l'auteur du 2026-11-17 : locales seulement, aucun envoi).

- Mesures de la machine : chaque point de l'Historique (toutes les 10 s) ; Historique desactive = pas d'alerte sur
  le disque, la memoire, le processeur, la temperature ni la batterie.
- Backends, incidents Active Defense et certificats : toutes les minutes (page Administration et echeances deja
  relevees, aucun calcul de plus).
- Chaque evenement : une ligne dans var/log/alertes.log et l'etat dans var/lib/admin/alertes.json."""
from __future__ import annotations

import asyncio
import contextlib
import time
from collections import deque
from collections.abc import Awaitable, Callable

from omega_serv.application.tls.certificate_inventory import CertificateLine
from omega_serv.domain.admin_web.alerts import AlertBook, AlertEvent, Reading
from omega_serv.ports.admin_alerts_port import AlertStorePort

SOURCES_SECONDS = 60.0
POINT_RULES = {"disque": "disk_used", "memoire": "mem", "swap": "swap", "processeur": "cpu", "temperature": "temp",
               "batterie": "battery"}
"""Regle -> cle du point d'historique."""
ERRORS_WINDOW_SECONDS = 300
ERRORS_MIN_REQUESTS = 50
"""Taux de 5xx sur les 5 dernieres minutes, seulement au-dela de 50 requetes (3 erreurs sur 4 visites n'alertent pas)."""


class AlertMonitor:
    def __init__(self, store: AlertStorePort, thresholds: Callable[[], dict[str, float | None]], *,
                 clock: Callable[[], float] = time.time) -> None:
        self._store = store
        self._thresholds = thresholds
        self._clock = clock
        try:
            saved = store.load()
        except OSError:
            saved = None
        self.book = AlertBook.from_dict(saved)
        self._window: deque[tuple[float, float, float]] = deque()
        """(instant, requetes, 5xx) des points recents (taux de 5xx glissant)."""

    @property
    def maintenance_until(self) -> float | None:
        try:
            until = self._store.maintenance_until()
        except OSError:
            return None
        return until if until is not None and until > self._clock() else None

    def on_point(self, point: dict[str, float | None], step: float = 10.0) -> None:
        readings = [Reading(rule, point.get(key)) for rule, key in POINT_RULES.items()]
        readings.append(Reading("erreurs_5xx", self._errors_rate(point, step)))
        self._apply(readings, frozenset())

    def _errors_rate(self, point: dict[str, float | None], step: float) -> float | None:
        rps, errors, at = point.get("rps"), point.get("e5xx"), point.get("t")
        if rps is None or errors is None or at is None:
            return None
        self._window.append((float(at), rps * step, errors * step))
        while self._window and self._window[0][0] <= float(at) - ERRORS_WINDOW_SECONDS:
            self._window.popleft()
        requests = sum(item[1] for item in self._window)
        if requests < ERRORS_MIN_REQUESTS:
            return 0.0
        return sum(item[2] for item in self._window) / requests * 100

    def on_sources(self, backends: list[tuple[str, str]] | None, incidents: list[str] | None,
                   certificates: list[CertificateLine] | None) -> None:
        """`backends` : (zone/nom, etat) ; `incidents` : identifiants ouverts ; None = source illisible (inchangee)."""
        readings: list[Reading] = []
        complete: set[str] = set()
        if backends is not None:
            complete.add("backend")
            readings += [Reading("backend", 1.0 if status == "down" else 0.0, name) for name, status in backends]
        if incidents is not None:
            complete.add("incident")
            readings += [Reading("incident", 1.0, incident) for incident in incidents]
        if certificates is not None:
            complete.add("certificat")
            readings += [Reading("certificat", float(line.days), line.path) for line in certificates
                         if line.days is not None]
        self._apply(readings, frozenset(complete))

    def _apply(self, readings: list[Reading], complete: frozenset[str]) -> None:
        events = self.book.evaluate(readings, self._thresholds(), self._clock(),
                                    maintenance=self.maintenance_until is not None, complete_rules=complete)
        if not events:
            return
        for event in events:
            self._store.log(_log_line(event))
        try:
            self._store.save(self.book.to_dict())
        except OSError:
            pass  # dossier non inscriptible : les alertes restent en memoire et dans le journal

    async def run(self, stop: asyncio.Event,
                  sources: Callable[[], Awaitable[tuple[list[tuple[str, str]] | None, list[str] | None,
                                                         list[CertificateLine] | None]]]) -> None:
        while not stop.is_set():
            with contextlib.suppress(Exception):  # une source illisible ne coupe jamais la surveillance
                self.on_sources(*await sources())
            try:
                await asyncio.wait_for(stop.wait(), SOURCES_SECONDS)
            except TimeoutError:
                pass


def _log_line(event: AlertEvent) -> str:
    """Journal en francais (comme error.log, D18b) : une ligne lisible et facile a filtrer."""
    alert = event.alert
    kind = {"opened": "ouverte", "worse": "aggravee", "closed": "fermee"}[event.kind]
    parts = [kind, alert.rule]
    if alert.subject:
        parts.append(f"sujet={alert.subject}")
    if alert.value is not None:
        parts.append(f"valeur={alert.value:g}")
    if alert.threshold is not None:
        parts.append(f"seuil={alert.threshold:g}")
    if alert.level:
        parts.append(f"palier={alert.level}")
    return " ".join(parts)
