"""Donnees du tableau de bord web dans le processus d'administration, lot 4 (plan §4 et §5.2).

Un seul calcul pour tous les navigateurs ouverts : `DashboardData.run` recalcule toutes les 2 s, et seulement si une
page a demande des donnees dans les 30 dernieres secondes (aucun travail quand personne ne regarde). Les appels lents
(gestionnaire de service, psutil, lecture des journaux, bases RIPOSTE et Active Defense) tournent dans un fil de
travail, un seul a la fois ; les mesures des backends passent par la route d'administration locale (lot 3 du
chantier 3). Les pages lisent le dernier resultat, deja mis en forme (dashboard_view.py).

Journaux (plan §5.2) : seulement les fichiers de la bibliotheque de l'instance, designes par un identifiant (jamais
un chemin envoye par le navigateur) ; instantane (N dernieres lignes, filtre) et direct (lignes ajoutees depuis une
position)."""
from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omega_serv.application.admin_web.dashboard_view import (
    Section,
    SecurityFacts,
    sections_payload,
    security_sections,
    server_state_sections,
    system_sections,
    traffic_sections,
)
from omega_serv.application.status.instance_status import BackendsSnapshot, InstanceStatusCollector
from omega_serv.core.i18n import _

REFRESH_SECONDS = 2.0
IDLE_SECONDS = 30.0
PANELS = ("etat", "flux", "ressources", "securite")
MAX_LINES = 2000
DEFAULT_LINES = 200


@dataclass(frozen=True)
class LogEntry:
    log_id: str
    label: str
    path: Path


def log_id_of(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


class DashboardData:
    def __init__(
        self,
        collector: InstanceStatusCollector,
        security: Callable[[], SecurityFacts],
        logs: Callable[[], list[LogEntry]],
        tail: Callable[[Path, int], tuple[list[str], int]],
        read_from: Callable[[Path, int], tuple[list[str], int, bool]],
        audit_lines: Callable[[int], list[str]],
        python_processes: Callable[[], int] = lambda: 1,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._collector = collector
        self._security = security
        self._logs = logs
        self._tail = tail
        self._read_from = read_from
        self._audit_lines = audit_lines
        self._python_processes = python_processes
        self._monotonic = monotonic
        self._last_wanted = -IDLE_SECONDS
        self._payloads: dict[str, dict[str, Any]] = {}
        self._summary: dict[str, Any] = {}
        self._opened = False

    # ------------------------------------------------------------------ rafraichissement
    def wanted(self) -> None:
        self._last_wanted = self._monotonic()

    def _collect(self, backends: BackendsSnapshot | None) -> dict[str, dict[str, Any]]:
        """Chaque colonne a part (retour de l'auteur du 2026-11-17) : une erreur de lecture dans l'une (droits du
        compte du service, fichier abime) ne vide plus les autres ; la colonne touchee affiche l'erreur."""
        collector = self._collector
        if not self._opened:
            collector.open()
            self._opened = True
        stamp = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")

        def attempt(build: Callable[[], Any]) -> tuple[Any, str]:
            try:
                return build(), ""
            except Exception as error:  # noqa: BLE001 - une colonne en erreur n'arrete jamais les autres
                return None, str(error)

        banned, _banned_error = attempt(collector.banned_counts)
        state, state_error = attempt(collector.server_state)
        traffic, traffic_error = attempt(collector.traffic)
        system, system_error = attempt(collector.system)
        since = collector.pending_sent_since
        if since is not None:
            attempt(lambda: collector.update_sent_bytes(since))
        facts, facts_error = attempt(self._security)

        def payload(error: str, build: Callable[[], list[Section]]) -> dict[str, Any]:
            if error:
                return {"sections": [], "error": error, "updated": stamp}
            sections, failure = attempt(build)
            if failure:
                return {"sections": [], "error": failure, "updated": stamp}
            return {**sections_payload(sections), "updated": stamp}

        self._summary = {
            "running": state.process.running if state is not None else None,
            "kind": state.config.kind if state is not None and state.config is not None else "",
            "rps": round(traffic.stats.rps_1m, 2) if traffic is not None else None,
            "errors_5xx": traffic.stats.errors_5xx if traffic is not None else None,
            "bans": banned[0] if banned is not None else None,
            "incidents": sum(1 for incident in facts.incidents if incident[2] == "open") if facts is not None else None,
            "updated": stamp,
        }
        return {
            "etat": payload(state_error, lambda: server_state_sections(state)),
            "flux": payload(traffic_error, lambda: traffic_sections(traffic, backends, banned,
                                                                   self._python_processes())),
            "ressources": payload(system_error, lambda: system_sections(system)),
            "securite": payload(facts_error, lambda: security_sections(facts)),
        }

    async def refresh_once(self) -> None:
        backends = await self._collector.backends()
        self._payloads = await asyncio.to_thread(self._collect, backends)

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            if self._monotonic() - self._last_wanted < IDLE_SECONDS:
                try:
                    await self.refresh_once()
                except Exception as error:  # noqa: BLE001 - une donnee imprevue ne coupe jamais le tableau de bord
                    self._payloads = {name: {"sections": [], "error": str(error)} for name in PANELS}
            try:
                await asyncio.wait_for(stop.wait(), REFRESH_SECONDS)
            except TimeoutError:
                pass

    def panel(self, name: str) -> dict[str, Any] | None:
        if name not in PANELS:
            return None
        self.wanted()
        return self._payloads.get(name, {"sections": [], "loading": _("Chargement...")})

    def summary(self) -> dict[str, Any]:
        """Une ligne de la page Instances d'un maitre (lot 6) : nombres bruts, mis en forme par le maitre."""
        self.wanted()
        return dict(self._summary) if self._summary else {"loading": True}

    # ------------------------------------------------------------------ journaux
    def log_list(self) -> list[dict[str, str]]:
        return [{"id": entry.log_id, "label": entry.label} for entry in self._logs()]

    def _entry(self, log_id: str) -> LogEntry | None:
        return next((entry for entry in self._logs() if entry.log_id == log_id), None)

    def log_snapshot(self, log_id: str, lines: int, contains: str) -> dict[str, Any] | None:
        entry = self._entry(log_id)
        if entry is None:
            return None
        try:
            found, size = self._tail(entry.path, MAX_LINES)
        except OSError as error:
            return {"label": entry.label, "lines": [], "cursor": 0,
                    "problem": _("Journal illisible pour le service : {error}").format(error=error.strerror or error)}
        if contains:
            needle = contains.lower()
            found = [line for line in found if needle in line.lower()]
        count = max(1, min(MAX_LINES, lines))
        return {"label": entry.label, "lines": found[-count:], "cursor": size}

    def log_follow(self, log_id: str, cursor: int) -> dict[str, Any] | None:
        entry = self._entry(log_id)
        if entry is None:
            return None
        try:
            lines, new_cursor, rotated = self._read_from(entry.path, max(0, cursor))
        except OSError as error:
            return {"lines": [], "cursor": cursor,
                    "problem": _("Journal illisible pour le service : {error}").format(error=error.strerror or error)}
        return {"lines": lines, "cursor": new_cursor,
                "rotated": _("Le journal a tourné : lecture reprise au début.") if rotated else ""}

    def audit(self, lines: int = DEFAULT_LINES) -> dict[str, Any]:
        try:
            return {"lines": self._audit_lines(max(1, min(MAX_LINES, lines)))}
        except OSError:
            return {"lines": []}
