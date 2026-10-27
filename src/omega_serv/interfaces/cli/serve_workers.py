"""Mode « boost » : plusieurs processus serveur (OMEGA-SERV_ETUDE_MODE_BOOST.md, decisions
utilisateur 2026-10-26).

Le processus principal :
- ouvre le port UNE fois et cree les compteurs de securite partages (option A) AVANT de lancer
  les workers, qui en heritent (fork) - le noyau repartit les connexions entre eux ;
- ecrit le fichier PID (le sien : c'est le `MainPID` vu par systemd) ;
- relaie SIGHUP (rechargement a chaud de chaque worker) et SIGTERM/SIGINT (arret propre de
  chacun, avec leur delai de grace), puis detruit la zone partagee ;
- relance un worker qui meurt, avec un garde-fou : trop de morts rapprochees = arret complet
  (jamais une boucle de relance infinie si la cause persiste).

Le nombre de workers ne change qu'au redemarrage (decision utilisateur) : un SIGHUP qui voit une
autre valeur l'ignore et le signale."""
from __future__ import annotations

import os
import signal
import socket
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_RESTART_WINDOW_SECONDS = 60.0
_MAX_RESTARTS_IN_WINDOW = 5
_CONTROL_SIGNALS = {signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGCHLD}


@dataclass(frozen=True)
class WorkerContext:
    index: int
    listen_socket: socket.socket
    shared_counters: Any


def effective_worker_count(configured: int, available_cores: int, recommended: int) -> tuple[int, str | None]:
    """0 = automatique (un par coeur physique, dans la limite des CPU disponibles). Au-dela des
    CPU de CETTE machine (config recopiee depuis une machine plus grosse), on se limite a eux et
    on le dit, plutot que de refuser de demarrer un serveur en production."""
    if configured == 0:
        return recommended, None
    if configured > available_cores:
        return available_cores, (
            f"server.workers = {configured} mais cette machine n'a que {available_cores} coeur(s) "
            f"disponible(s) : {available_cores} worker(s) lance(s)"
        )
    return configured, None


def open_listen_socket(bind: str, port: int, backlog: int) -> socket.socket:
    family = socket.AF_INET6 if ":" in bind else socket.AF_INET
    listen_socket = socket.create_server((bind, port), family=family, backlog=backlog)
    listen_socket.set_inheritable(True)
    return listen_socket


def run_workers(
    worker_count: int,
    listen_socket: socket.socket,
    shared_counters: Any,
    run_worker: Callable[[WorkerContext], int],
    grace_period_seconds: int,
    read_configured_workers: Callable[[], int | None],
) -> int:
    signal.pthread_sigmask(signal.SIG_BLOCK, _CONTROL_SIGNALS)
    children: dict[int, int] = {}  # pid -> numero du worker
    deaths: list[float] = []

    def spawn(index: int) -> None:
        pid = os.fork()
        if pid == 0:
            code = 1
            try:
                signal.pthread_sigmask(signal.SIG_UNBLOCK, _CONTROL_SIGNALS)
                code = run_worker(WorkerContext(index, listen_socket, shared_counters))
            except BaseException as exc:  # noqa: BLE001 - un worker ne remonte jamais dans le code du principal
                print(f"Worker {index} arrete sur erreur : {exc!r}", file=sys.stderr)
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(code)
        children[pid] = index

    for index in range(1, worker_count + 1):
        spawn(index)
    print(f"OMEGA-SERV : {worker_count} worker(s) lance(s)")

    stopping = False
    failed = False
    stop_deadline = 0.0
    while children:
        info = signal.sigtimedwait(_CONTROL_SIGNALS, 1.0)
        if info is not None and info.si_signo in (signal.SIGTERM, signal.SIGINT) and not stopping:
            stopping = True
            stop_deadline = time.monotonic() + grace_period_seconds + 5
            print("Arret demande - transmis aux workers...")
            _signal_all(children, signal.SIGTERM)
        elif info is not None and info.si_signo == signal.SIGHUP and not stopping:
            configured = read_configured_workers()
            if configured is not None and configured not in (worker_count, 0):
                print(
                    f"server.workers modifie ({configured}) : pris en compte au prochain redemarrage complet",
                    file=sys.stderr,
                )
            _signal_all(children, signal.SIGHUP)
        for pid, index in _reap(children):
            if stopping:
                continue
            now = time.monotonic()
            deaths[:] = [t for t in deaths if now - t < _RESTART_WINDOW_SECONDS] + [now]
            if len(deaths) > _MAX_RESTARTS_IN_WINDOW:
                print(
                    f"Trop d'arrets de workers en {int(_RESTART_WINDOW_SECONDS)} s : arret complet du service",
                    file=sys.stderr,
                )
                stopping = failed = True
                stop_deadline = time.monotonic() + grace_period_seconds + 5
                _signal_all(children, signal.SIGTERM)
                continue
            print(f"Worker {index} (PID {pid}) arrete de facon inattendue : relance", file=sys.stderr)
            spawn(index)
        if stopping and children and time.monotonic() > stop_deadline:
            print(f"{len(children)} worker(s) arrete(s) de force apres le delai de grace.", file=sys.stderr)
            _signal_all(children, signal.SIGKILL)
    return 1 if failed else 0


def _signal_all(children: dict[int, int], sig: signal.Signals) -> None:
    for pid in list(children):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass


def _reap(children: dict[int, int]) -> list[tuple[int, int]]:
    ended: list[tuple[int, int]] = []
    while children:
        try:
            pid, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid == 0:
            break
        index = children.pop(pid, None)
        if index is not None:
            ended.append((pid, index))
    return ended
