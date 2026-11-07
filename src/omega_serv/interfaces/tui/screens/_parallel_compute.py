"""Repartit les taches de lecture (application/logs/log_tasks.py) sur le pool de processus et fusionne
leurs agregats DANS L'ORDRE des taches (resultat identique a une lecture d'un bloc) - commun a
Statistiques et « Voir et traiter IP ». Porte d'omega-log le 2026-11-07.

Un log illisible par votre compte (apres authentification) est LU avec sudo par le processus principal,
dans un thread, puis seulement ANALYSE dans le pool (2026-11-07) : un processus du pool ne lance jamais sudo.

Progression REELLE : `on_progress(octets_faits, octets_total, taches_faites, taches_total)` a chaque
morceau termine. Annulation (ecran ferme, Textual annule son worker) : les morceaux pas encore demarres
sont annules, jamais lances pour rien. Une erreur d'un morceau (LogPermissionError notamment) annule les
autres et remonte telle quelle a l'ecran."""
from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import TYPE_CHECKING

from omega_serv.application.logs.log_tasks import (
    ReadTask,
    accumulate_text,
    plan_read_tasks,
    run_read_task,
)
from omega_serv.application.logs.privileged_logs import read_privileged
from omega_serv.application.logs.process_pool import POOL_WORKERS, stats_pool
from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.stats_accumulator import StatsAccumulator

if TYPE_CHECKING:
    from omega_serv.ports.process_runner_port import ProcessRunnerPort


async def _run_one(task: ReadTask, runner: ProcessRunnerPort | None) -> StatsAccumulator:
    loop = asyncio.get_running_loop()
    if task.privileged:
        if runner is None:
            raise LogPermissionError(task.path)
        # Lecture sudo dans CE processus (un thread : c'est de l'attente), analyse dans le pool.
        text = await loop.run_in_executor(None, read_privileged, runner, task.path)
        return await loop.run_in_executor(stats_pool(), functools.partial(accumulate_text, text, task.path, task.cutoff))
    return await loop.run_in_executor(stats_pool(), functools.partial(run_read_task, task))


async def run_read_tasks(
    tasks: list[ReadTask], on_progress: Callable[[int, int, int, int], None] | None = None,
    runner: ProcessRunnerPort | None = None,
) -> StatsAccumulator:
    futures = [asyncio.ensure_future(_run_one(task, runner)) for task in tasks]
    index_of = {future: index for index, future in enumerate(futures)}
    results: list[StatsAccumulator | None] = [None] * len(tasks)
    total_weight = sum(task.weight for task in tasks)
    done_weight, done_tasks = 0, 0
    pending = set(futures)
    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for future in done:
                index = index_of[future]
                results[index] = future.result()  # leve l'erreur du morceau, le finally annule les autres
                done_weight += tasks[index].weight
                done_tasks += 1
            if on_progress is not None:
                on_progress(done_weight, total_weight, done_tasks, len(tasks))
    finally:
        for future in pending:
            future.cancel()
    total = StatsAccumulator()
    for result in results:
        if result is not None:
            total.merge(result)
    return total


async def accumulate_in_pool(
    paths: list[str], period: str | None, on_progress: Callable[[int, int, int, int], None] | None = None,
    runner: ProcessRunnerPort | None = None,
) -> StatsAccumulator:
    """Planifie (processus principal, rapide) puis execute en parallele. LogPermissionError possible des la
    planification (fichier illisible) si `runner` est None ; avec `runner` (sudo authentifie), le fichier
    illisible est lu avec sudo."""
    tasks = plan_read_tasks(paths, period=period, workers=POOL_WORKERS, privileged=runner is not None)
    if on_progress is not None:
        on_progress(0, sum(task.weight for task in tasks), 0, len(tasks))
    return await run_read_tasks(tasks, on_progress, runner)
