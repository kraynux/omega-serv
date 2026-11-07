"""Lecture des logs en taches paralleles pour Statistiques et « Voir et traiter IP » - porte d'omega-log
le 2026-11-07 (OMEGA-SERV_A_FAIRE_STATS_DEPUIS_OMEGA_LOG.md, lot 1). Un log illisible leve
LogPermissionError ; apres authentification a l'ecran (`runner` fourni), il est lu avec sudo
(application/logs/privileged_logs.py) en une seule tache, filtree ensuite sur la periode.

- `plan_read_tasks` (processus principal, rapide) : decoupe chaque fichier lu en entier en morceaux
  ALIGNES sur des fins de ligne (aucune ligne coupee en deux, aucune comptee deux fois) ;
- `run_read_task` (un processus du pool par morceau) : lit son morceau en flux, analyse chaque ligne et
  rend un `StatsAccumulator` - jamais la liste des lignes ;
- l'appelant fusionne les accumulateurs dans l'ordre des taches : resultat identique a une lecture d'un bloc.

Periodes 24h/7j/30j : une seule tache par fichier, lecture depuis la FIN avec arret anticipe (deja rapide,
voir reading.py)."""
from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import pairwise
from typing import TYPE_CHECKING

from omega_serv.application.logs.privileged_logs import read_privileged
from omega_serv.application.logs.reading import (
    _MAX_CONSECUTIVE_OLD_LINES,
    PERIOD_TO_TIMEDELTA,
    _iter_lines_reverse,
)
from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.parser import parse_log_line
from omega_serv.domain.logs.stats_accumulator import StatsAccumulator

if TYPE_CHECKING:
    from omega_serv.ports.process_runner_port import ProcessRunnerPort

MIN_CHUNK_BYTES = 8 * 1024 * 1024
"""Sous 8 Mo, un fichier reste en un morceau : le lancement d'une tache coute plus que l'analyse."""
_BLOCK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ReadTask:
    path: str
    start: int = 0
    end: int | None = None
    """Octets [start, end) du fichier ; end None = jusqu'a la fin."""
    period: str | None = None
    cutoff: datetime | None = None
    privileged: bool = False
    """Lu avec sudo (log illisible par votre compte) : une seule tache, fichier entier."""
    weight: int = 0
    """Octets couverts, pour la progression affichee (0 si inconnu)."""


def _aligned_boundaries(path: str, size: int, parts: int) -> list[int]:
    """Bornes des morceaux, chacune juste apres une fin de ligne."""
    bounds = [0]
    with open(path, "rb") as handle:
        for index in range(1, parts):
            handle.seek(size * index // parts)
            handle.readline()
            position = handle.tell()
            if bounds[-1] < position < size:
                bounds.append(position)
    bounds.append(size)
    return bounds


def plan_read_tasks(
    paths: list[str], *, period: str | None = None, now: datetime | None = None, workers: int = 1,
    privileged: bool = False,
) -> list[ReadTask]:
    """Taches de lecture de `paths`. Leve LogPermissionError pour un fichier illisible, sauf si
    `privileged` (authentification sudo deja faite) : il devient une tache lue avec sudo."""
    cutoff = (now or datetime.now(timezone.utc)) - PERIOD_TO_TIMEDELTA[period] if period is not None else None
    tasks: list[ReadTask] = []
    for path in paths:
        try:
            size = os.path.getsize(path)
            readable = os.access(path, os.R_OK)
        except OSError:
            continue  # absent : rien a lire (meme comportement qu'avant)
        if not readable:
            if not privileged:
                raise LogPermissionError(path)
            tasks.append(ReadTask(path, period=period, cutoff=cutoff, privileged=True, weight=size))
            continue
        if period is not None:
            tasks.append(ReadTask(path, period=period, cutoff=cutoff, weight=size))
            continue
        parts = max(1, min(workers * 4, size // MIN_CHUNK_BYTES))
        try:
            bounds = _aligned_boundaries(path, size, parts) if parts > 1 else [0, size]
        except PermissionError:
            raise LogPermissionError(path) from None
        except OSError:
            continue
        tasks.extend(ReadTask(path, start, end, weight=end - start) for start, end in pairwise(bounds))
    return tasks


def _iter_range(path: str, start: int, end: int | None) -> Iterator[str]:
    """Lignes des octets [start, end), lues par blocs de 1 Mo (jamais tout le morceau d'un coup)."""
    with open(path, "rb") as handle:
        handle.seek(start)
        remaining = None if end is None else end - start
        rest = b""
        while remaining is None or remaining > 0:
            block = handle.read(_BLOCK_BYTES if remaining is None else min(_BLOCK_BYTES, remaining))
            if not block:
                break
            if remaining is not None:
                remaining -= len(block)
            lines = (rest + block).split(b"\n")
            rest = lines.pop()
            for raw in lines:
                yield raw.decode("utf-8", errors="replace")
        if rest:
            yield rest.decode("utf-8", errors="replace")


def run_read_task(task: ReadTask, runner: ProcessRunnerPort | None = None) -> StatsAccumulator:
    """Execute dans un processus du pool : analyse les lignes du morceau, rend leurs agregats."""
    accumulator = StatsAccumulator()
    if task.privileged:
        if runner is None:
            raise LogPermissionError(task.path)
        return accumulate_text(read_privileged(runner, task.path), task.path, task.cutoff)
    try:
        if task.period is not None:
            _accumulate_period(task, accumulator)
        else:
            for line in _iter_range(task.path, task.start, task.end):
                entry = parse_log_line(line, log_path=task.path)
                if entry is not None:
                    accumulator.add(entry)
    except PermissionError:
        raise LogPermissionError(task.path) from None
    except OSError:
        pass
    return accumulator


def accumulate_text(text: str, path: str, cutoff: datetime | None) -> StatsAccumulator:
    """Analyse d'un log deja lu avec sudo par le processus PRINCIPAL (2026-11-07) : les processus du pool ne
    lancent jamais sudo eux-memes - avec `timestamp_type=ppid` dans sudoers, ils ne verraient pas
    l'authentification que vous venez de faire."""
    accumulator = StatsAccumulator()
    for line in text.splitlines():
        entry = parse_log_line(line, log_path=path)
        if entry is not None and (cutoff is None or entry.timestamp >= cutoff):
            accumulator.add(entry)
    return accumulator


def _accumulate_period(task: ReadTask, accumulator: StatsAccumulator) -> None:
    """Depuis la fin du fichier, arret apres _MAX_CONSECUTIVE_OLD_LINES lignes consecutives trop anciennes
    (meme regle que reading._read_entries_for_period)."""
    assert task.cutoff is not None
    consecutive_old = 0
    for raw_line in _iter_lines_reverse(task.path):
        entry = parse_log_line(raw_line, log_path=task.path)
        if entry is None:
            continue
        if entry.timestamp >= task.cutoff:
            accumulator.add(entry)
            consecutive_old = 0
        else:
            consecutive_old += 1
            if consecutive_old >= _MAX_CONSECUTIVE_OLD_LINES:
                break


def accumulate_paths(
    paths: list[str], *, period: str | None = None, now: datetime | None = None,
    runner: ProcessRunnerPort | None = None,
) -> StatsAccumulator:
    """Version sequentielle (tests, export) : memes taches, executees une par une ici."""
    total = StatsAccumulator()
    for task in plan_read_tasks(paths, period=period, now=now, privileged=runner is not None):
        total.merge(run_read_task(task, runner))
    return total
