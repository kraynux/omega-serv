"""Trafic des sites pour l'historique (plan tableau de bord web §9.5, lot 9b) : additionne les fichiers
var/run/traffic/<pid>.json publies par les processus serveur (moteur Python, workers, processus de securite, natif).

Chaque processus publie ses cumuls depuis son lancement. On suit chaque PID : un PID vu pour la premiere fois sert
de point de depart seulement s'il publiait deja a la toute premiere lecture (jamais le passe du serveur recompte) ;
apparu ensuite (premier visiteur apres le demarrage, natif relance, nouveau worker) ou ne apres le demarrage du
processus d'administration, il compte depuis zero (sinon la premiere salve de trafic etait perdue). Un cumul qui recule (compteur reparti
de zero) repart de sa nouvelle valeur. Le total rendu ne fait que croitre. Aucun fichier jamais vu : None
(pas de mesure sur cette machine, graphes masques) ; serveur arrete apres coup : le total reste, debit nul."""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import psutil

from omega_serv.infrastructure.server.traffic_meter import TRAFFIC_RELATIVE_DIR

STALE_SECONDS = 3600.0


def _started_at(pid: int) -> float | None:
    try:
        return float(psutil.Process(pid).create_time())
    except (psutil.Error, OSError):
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class TrafficTotals:
    def __init__(self, project_root: Path, alive: Callable[[int], bool] = _alive,
                 clock: Callable[[], float] = time.time,
                 started_at: Callable[[int], float | None] = _started_at) -> None:
        self._directory = project_root / TRAFFIC_RELATIVE_DIR
        self._alive = alive
        self._clock = clock
        self._started_at = started_at
        self._since = clock()
        self._last: dict[int, tuple[int, int]] = {}
        self._seen = False
        self._first_read = True
        self.received = 0
        self.sent = 0

    def read(self) -> tuple[int, int] | None:
        current: dict[int, tuple[int, int]] = {}
        try:
            entries = list(os.scandir(self._directory))
        except OSError:
            entries = []
        for entry in entries:
            name = entry.name
            if name.startswith(".") or not name.endswith(".json") or not name[:-5].isdigit():
                continue
            pid = int(name[:-5])
            if not self._alive(pid):
                self._remove_if_stale(entry)
                continue
            values = self._load(Path(entry.path))
            if values is None:
                continue
            current[pid] = values
            before = self._last.get(pid)
            if before is None:
                born = self._started_at(pid)
                fresh = not self._first_read or (born is not None and born >= self._since)
                before = (0, 0) if fresh else None
            if before is not None:
                self.received += max(0, values[0] - before[0]) if values[0] >= before[0] else 0
                self.sent += max(0, values[1] - before[1]) if values[1] >= before[1] else 0
        self._last = current
        self._first_read = False
        self._seen = self._seen or bool(current)
        return (self.received, self.sent) if self._seen else None

    @staticmethod
    def _load(path: Path) -> tuple[int, int] | None:
        try:
            data = json.loads(path.read_text(encoding="ascii"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        received, sent = data.get("recu"), data.get("envoye")
        if not isinstance(received, int) or not isinstance(sent, int) or isinstance(received, bool) \
                or isinstance(sent, bool) or received < 0 or sent < 0:
            return None
        return received, sent

    def _remove_if_stale(self, entry: os.DirEntry[str]) -> None:
        """Processus mort sans avoir retire son fichier (arret brutal) : retire au bout d'une heure."""
        try:
            if self._clock() - entry.stat().st_mtime > STALE_SECONDS:
                os.unlink(entry.path)
        except OSError:
            pass
