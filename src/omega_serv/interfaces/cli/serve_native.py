"""Superviseur du moteur natif (`serve` avec server.engine = "native" ; plan moteur C++ lot 3, §6 et §16.5).

Deroulement :
- la socket d'ecoute est ouverte ICI, une seule fois, et confiee au natif (`--listen-fd`) : jamais deux moteurs
  sur le port ;
- echec du natif AVANT son premier acquittement (binaire qui ne repond pas, contrat different, configuration
  refusee...) : `start_native` rend None, le natif est deja arrete, la socket fermee - `cmd_serve` lance alors
  le moteur Python (repli au demarrage, signale) ;
- SIGHUP : configuration relue ; tout changement que le natif ne peut pas appliquer a chaud (moteur, fonction non
  prise en charge, bind / port / TLS) est REFUSE avec « redemarrage complet necessaire » - l'ancienne
  generation reste active, jamais un etat melange ;
- plantage en cours de route : relance (meme socket), au plus MAX_RESTARTS dans RESTART_WINDOW_SECONDS, puis
  arret propre avec message - jamais de bascule a chaud vers Python (plan D5) ;
- SIGTERM / SIGINT : SHUTDOWN au natif (drainage borne), arret de RIPOSTE, fichier PID retire ;
- lot 4 : si leurres, WAF, Active Defense ou Auth sont actifs, un processus Python de securite (fork, sans fil
  d'execution dans le superviseur) recoit un canal par fil natif ; il est relance s'il s'arrete (nouveaux canaux
  confies au natif par DATA_ATTACH), recharge sur SIGHUP, arrete avec le natif."""
from __future__ import annotations

import os
import signal
import socket
import sys
import time
import traceback
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.engine_selection import (
    NATIVE_BINARY_RELATIVE_PATH,
    EngineDecision,
    decide_engine,
    log_reason,
)
from omega_serv.application.server.engine_state import EngineState, write_engine_state
from omega_serv.application.server.start_server import build_server, try_reload_server
from omega_serv.application.services.pid_file import remove_pid_file, write_pid_file
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.platform_info import cpu_info
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.logging.access_log_format import format_error_log_line
from omega_serv.infrastructure.process.native_engine_process import native_binary_problem
from omega_serv.infrastructure.server.native_engine import NativeEngine, NativeStartError
from omega_serv.infrastructure.server.native_ipc import data_channel_pair
from omega_serv.infrastructure.server.native_snapshot import (
    inspect_section,
    native_inspect_body_notice,
)
from omega_serv.infrastructure.server.security_worker import run_security_worker
from omega_serv.infrastructure.waf.shared_counters import SharedCounters
from omega_serv.interfaces.cli.serve_workers import effective_worker_count, open_listen_socket

MAX_RESTARTS = 5
RESTART_WINDOW_SECONDS = 60.0
STATE_REFRESH_SECONDS = 2.0


def native_binary_path(container: DependencyContainer) -> Path:
    return container.project_root / NATIVE_BINARY_RELATIVE_PATH


def current_decision(config: OmegaServConfig, container: DependencyContainer) -> EngineDecision:
    return decide_engine(config, native_binary_problem(native_binary_path(container)))


def log_error_line(container: DependencyContainer, config: OmegaServConfig, message: str) -> None:
    try:
        container.logger.append_line(
            container.project_root / config.logs.error, format_error_log_line(datetime.now(timezone.utc), message),
        )
    except OSError:
        pass


def native_thread_count() -> int:
    """Fils du natif = coeurs utilisables par ce processus (un canal de securite par fil)."""
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        return max(1, os.cpu_count() or 1)


class SecurityProcess:
    """Processus Python de securite (lot 4) : `fork` du superviseur (mono-fil), qui construit SON serveur Python
    (`build_server`, aucun port ecoute) et sert les INSPECT de tous les fils du natif."""

    def __init__(self, container: DependencyContainer, config_path: Path, counters: SharedCounters | None = None) -> None:
        self.container = container
        self.config_path = config_path
        self.counters = counters  # plusieurs processus de securite : compteurs partages (rate limit, reputation), comme le mode boost
        self.pid: int | None = None

    def start(self, config: OmegaServConfig, channels: int, close_in_child: list[int]) -> list[socket.socket]:
        """Rend les extremites « natif » des canaux (a transmettre puis fermer par l'appelant)."""
        pairs = [data_channel_pair() for _ in range(channels)]  # correctif 2.6.2 (D20) : tampons agrandis
        pid = os.fork()
        if pid == 0:  # processus de securite
            code = 1
            try:
                for native_end, _worker_end in pairs:
                    native_end.close()
                for fd in close_in_child:  # socket d'ecoute, canal de controle : jamais gardes ici
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                code = self._serve(config, [worker_end.detach() for _native_end, worker_end in pairs])
            except BaseException:  # noqa: BLE001 - un fils ne remonte jamais dans le code du superviseur
                traceback.print_exc()
            finally:
                os._exit(code)
        for _native_end, worker_end in pairs:
            worker_end.close()
        self.pid = pid
        return [native_end for native_end, _worker_end in pairs]

    def _serve(self, config: OmegaServConfig, channel_fds: list[int]) -> int:
        container = self.container
        server = build_server(config, container.project_root, container.filesystem, container.logger, container.clock,
                              shared_counters=self.counters)

        def reload() -> None:
            result = load_config(container.configuration, self.config_path)
            if not result.success or result.config is None:
                print("processus de securite : rechargement refuse (configuration invalide)", file=sys.stderr)
                return
            error = try_reload_server(server, result.config, container.project_root, container.filesystem, container.clock)
            if error is not None:
                print(f"processus de securite : rechargement REFUSE - regles precedentes actives : {error}", file=sys.stderr)

        return run_security_worker(server, channel_fds, reload)

    def alive(self) -> bool:
        if self.pid is None:
            return False
        try:
            pid, _status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            pid = self.pid
        if pid == self.pid:
            self.pid = None
            return False
        return True

    def signal(self, sig: signal.Signals) -> None:
        if self.pid is not None:
            try:
                os.kill(self.pid, sig)
            except ProcessLookupError:
                pass

    def stop(self, timeout: float) -> None:
        self.signal(signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while self.alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.alive():
            self.signal(signal.SIGKILL)
            while self.alive():
                time.sleep(0.05)


class SecurityPool:
    """Lot 7 : N processus de securite. Le fil natif i est servi par le processus i % N ; les
    compteurs (rate limit, reputation) sont partages entre eux par le MEME mecanisme que le mode boost
    (SharedCounters, memoire partagee + verrous herites par fork)."""

    def __init__(self, container: DependencyContainer, config_path: Path, processes: int, counters: SharedCounters | None) -> None:
        self.members = [SecurityProcess(container, config_path, counters) for _ in range(max(1, processes))]

    def _threads_of(self, member: int, threads: int) -> list[int]:
        return [i for i in range(threads) if i % len(self.members) == member]

    @property
    def pids(self) -> list[int]:
        return [m.pid for m in self.members if m.pid is not None]

    @property
    def pid(self) -> int | None:
        return self.members[0].pid

    def start(self, config: OmegaServConfig, threads: int, close_in_child: list[int]) -> list[socket.socket]:
        """Extremites « natif » rangees par rang de fil (a transmettre puis fermer par l'appelant)."""
        ends: list[socket.socket | None] = [None] * threads
        for index, member in enumerate(self.members):
            ranks = self._threads_of(index, threads)
            for rank, end in zip(ranks, member.start(config, len(ranks), close_in_child), strict=True):
                ends[rank] = end
        assert all(end is not None for end in ends)
        return [end for end in ends if end is not None]

    def alive(self) -> bool:
        return all(member.alive() for member in self.members)

    def restart_dead(self, config: OmegaServConfig, threads: int, close_in_child: list[int]) -> list[tuple[int, socket.socket]]:
        """Relance les processus arretes ; rend (rang du fil, nouvelle extremite) a confier au natif."""
        attached: list[tuple[int, socket.socket]] = []
        for index, member in enumerate(self.members):
            if member.alive():
                continue
            ranks = self._threads_of(index, threads)
            attached += list(zip(ranks, member.start(config, len(ranks), close_in_child), strict=True))
        return attached

    def signal(self, sig: signal.Signals) -> None:
        for member in self.members:
            member.signal(sig)

    def stop(self, timeout: float) -> None:
        for member in self.members:
            member.signal(signal.SIGTERM)
        for member in self.members:
            member.stop(timeout)


def _restart_blocker(old: OmegaServConfig, new: OmegaServConfig) -> str | None:
    """Ce qu'un rechargement a chaud ne peut pas changer avec le natif (socket et TLS fixes au demarrage)."""
    for label, before, after in (
        ("server.bind", old.server.bind, new.server.bind),
        ("server.port", old.server.port, new.server.port),
        ("server.listen_backlog", old.server.listen_backlog, new.server.listen_backlog),
        ("tls", old.tls, new.tls),  # certificat, cle, versions : charges une fois au demarrage, comme Python
        ("server.workers", old.server.workers, new.server.workers),  # nombre de processus de securite
        # lot 4 : le processus de securite et ses canaux existent ou non des le demarrage
        ("leurres / WAF / Active Defense / Auth (activation)", inspect_section(old) is None, inspect_section(new) is None),
    ):
        if before != after:
            return label
    return None


class NativeSupervisor:
    def __init__(self, config: OmegaServConfig, config_path: Path, container: DependencyContainer,
                 decision: EngineDecision, riposte: object | None) -> None:
        self.config = config
        self.config_path = config_path
        self.container = container
        self.decision = decision
        self.riposte = riposte
        self.threads = native_thread_count()
        self.engine = NativeEngine(native_binary_path(container), container.project_root, threads=self.threads)
        # Lot 7 : server.workers = nombre de processus de securite, ramene au maximum du natif sur cette machine
        # (engine_levels.max_workers : 2 a partir de 4 coeurs physiques, sinon 1 - plan §25), et aux fils natifs
        # (chacun sert au moins un fil).
        cpu = cpu_info()
        workers, capped = effective_worker_count(config.server.workers, "native", cpu.usable_cores)
        if capped:
            print(capped, file=sys.stderr)
            log_error_line(container, config, capped)
        self.security_processes = max(1, min(workers, self.threads))
        self.counters: SharedCounters | None = None
        self.security: SecurityPool | None = None
        if inspect_section(config) is not None:
            if self.security_processes > 1:
                self.counters = SharedCounters.create(f"omega_serv_{config.server.port}")
            self.security = SecurityPool(container, config_path, self.security_processes, self.counters)
        self.security_restarts = 0
        self.listen_socket: socket.socket | None = None
        self.restarts = 0
        self.last_reload = ""
        self._stop = False
        self._reload = False

    # ------------------------------------------------------------------ demarrage
    def start(self) -> str | None:
        """None si le natif sert ; sinon la cause (natif arrete, socket fermee : repli Python possible)."""
        self._notice_inspect_body_limit(self.config)
        self.listen_socket = open_listen_socket(self.config.server.bind, self.config.server.port,
                                                self.config.server.listen_backlog)
        self.listen_socket.set_inheritable(False)  # transmise au natif seulement, le temps du lancement
        try:
            self._start_engine()
        except NativeStartError as e:
            self.listen_socket.close()
            self.listen_socket = None
            if self.counters is not None:  # repli Python (mode boost) : il cree ses propres compteurs, meme nom
                self.counters.destroy()
                self.counters = None
            return f"{e.code} : {e.detail}"
        return None

    def _start_engine(self) -> None:
        """Natif (+ processus de securite et ses canaux si besoin). NativeStartError : tout est deja arrete."""
        assert self.listen_socket is not None
        data: list[socket.socket] = []
        if self.security is not None:
            self.security.stop(5.0)  # un ancien processus (natif relance) n'a plus de canal valide
            data = self.security.start(self.config, self.threads, [self.listen_socket.fileno()])
        try:
            self.engine.start(self.config, [self.listen_socket.fileno()], [s.fileno() for s in data])
        except NativeStartError:
            if self.security is not None:
                self.security.stop(5.0)
            raise
        finally:
            for s in data:
                s.close()

    def _restart_security(self) -> None:
        """Processus de securite arrete, natif vivant : nouveaux canaux confies au natif (DATA_ATTACH)."""
        assert self.security is not None and self.listen_socket is not None
        inherited = [self.listen_socket.fileno(), self.engine.control_fd()]  # le canal de controle surtout :
        # garde ouvert dans ce fils, il empecherait le natif de voir la disparition du superviseur
        data = self.security.restart_dead(self.config, self.threads, [fd for fd in inherited if fd >= 0])
        try:
            for index, channel in data:
                self.engine.attach_data_channel(index, channel.fileno())
        finally:
            for _index, channel in data:
                channel.close()
        self.security_restarts += 1

    # ------------------------------------------------------------------ boucle
    def run(self) -> int:
        container = self.container
        pid_path = container.project_root / "var" / "run" / "omega-serv.pid"
        write_pid_file(container.filesystem, pid_path, os.getpid())
        print(f"OMEGA-SERV a l'ecoute sur {self.config.server.bind}:{self.config.server.port} "
              f"(moteur natif {self.engine.binary_version}, PID {self.engine.process.pid if self.engine.process else '?'})")
        previous = {sig: signal.signal(sig, self._on_signal) for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
        deaths: deque[float] = deque()
        security_deaths: deque[float] = deque()
        exit_code = 0
        if self.riposte is not None:
            self.riposte.start()  # type: ignore[attr-defined]
        self._write_state()  # visible des le demarrage (ecran Etat, engine status)
        next_state = time.monotonic() + STATE_REFRESH_SECONDS
        try:
            while True:
                self.engine.pump(1.0)
                if self.riposte is not None:
                    self.riposte.tick()  # type: ignore[attr-defined]
                if self._stop:
                    break
                if self._reload:
                    self._reload = False
                    self._handle_reload()
                if not self.engine.alive():
                    status = self.engine.process.returncode if self.engine.process else None
                    now = time.monotonic()
                    deaths.append(now)
                    while deaths and now - deaths[0] > RESTART_WINDOW_SECONDS:
                        deaths.popleft()
                    message = f"moteur natif arrete de facon inattendue (code {status})"
                    print(message, file=sys.stderr)
                    log_error_line(container, self.config, message)
                    if len(deaths) > MAX_RESTARTS:
                        message = (f"moteur natif arrete {len(deaths)} fois en {RESTART_WINDOW_SECONDS:.0f} s : "
                                   "arret du serveur (aucune bascule a chaud vers le moteur Python)")
                        print(message, file=sys.stderr)
                        log_error_line(container, self.config, message)
                        exit_code = 1
                        break
                    assert self.listen_socket is not None
                    try:
                        self._start_engine()
                        self.restarts += 1
                        print(f"moteur natif relance (PID {self.engine.process.pid if self.engine.process else '?'})")
                    except NativeStartError as e:
                        log_error_line(container, self.config, f"relance du moteur natif impossible : {e.code} : {e.detail}")
                if self.security is not None and self.engine.alive() and not self.security.alive():
                    now = time.monotonic()
                    security_deaths.append(now)
                    while security_deaths and now - security_deaths[0] > RESTART_WINDOW_SECONDS:
                        security_deaths.popleft()
                    message = "processus de securite arrete de facon inattendue"
                    print(message, file=sys.stderr)
                    log_error_line(container, self.config, message)
                    if len(security_deaths) > MAX_RESTARTS:
                        message = (f"processus de securite arrete {len(security_deaths)} fois en "
                                   f"{RESTART_WINDOW_SECONDS:.0f} s : arret du serveur")
                        print(message, file=sys.stderr)
                        log_error_line(container, self.config, message)
                        exit_code = 1
                        break
                    self._restart_security()
                    print(f"processus de securite relance (PID {', '.join(map(str, self.security.pids))})")
                if time.monotonic() >= next_state:
                    self._write_state()
                    next_state = time.monotonic() + STATE_REFRESH_SECONDS
        finally:
            print("Arret demande - drainage des connexions en cours...")
            self.engine.stop(float(self.config.server.shutdown_grace_period_seconds))
            if self.security is not None:
                self.security.stop(5.0)
            if self.counters is not None:
                self.counters.destroy()
            if self.riposte is not None:
                self.riposte.stop()  # type: ignore[attr-defined]
            if self.listen_socket is not None:
                self.listen_socket.close()
            remove_pid_file(container.filesystem, pid_path)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        return exit_code

    def _on_signal(self, signum: int, _frame: object) -> None:
        if signum == signal.SIGHUP:
            self._reload = True
        else:
            self._stop = True

    # ------------------------------------------------------------------ rechargement
    def _handle_reload(self) -> None:
        print("Rechargement demande (SIGHUP) - moteur natif...")
        if self.riposte is not None:
            self.riposte.reload()  # type: ignore[attr-defined]
        result = load_config(self.container.configuration, self.config_path)
        if not result.success or result.config is None:
            self._refuse("configuration invalide : " + "; ".join(result.errors))
            return
        new = result.config
        decision = current_decision(new, self.container)
        if decision.effective != "native":
            causes = ", ".join(log_reason(r) for r in decision.reasons) or "moteur python demande"
            self._refuse(f"la nouvelle configuration exige le moteur Python ({causes}) - redemarrage complet necessaire")
            return
        blocker = _restart_blocker(self.config, new)
        if blocker is not None:
            self._refuse(f"{blocker} modifie - redemarrage complet necessaire")
            return
        error = self.engine.reload(new)
        if error is not None:
            self._refuse(f"configuration refusee par le moteur natif : {error}")
            return
        if self.security is not None:
            self.security.signal(signal.SIGHUP)  # regles WAF, zones Auth... relues comme par le moteur Python
        self.config = new
        self.decision = decision
        self._notice_inspect_body_limit(new)
        self.last_reload = f"generation {self.engine.generation} active"
        print(f"Rechargement termine (generation {self.engine.generation}).")
        self._write_state()

    def _notice_inspect_body_limit(self, config: OmegaServConfig) -> None:
        """Correctif 2.6.2 (D20) : body_max_inspect_bytes au-dela de ce que la trame INSPECT peut porter."""
        notice = native_inspect_body_notice(config)
        if notice is not None:
            print(notice, file=sys.stderr)
            log_error_line(self.container, config, notice)

    def _refuse(self, reason: str) -> None:
        message = f"Rechargement REFUSE - la configuration precedente reste active : {reason}"
        print(message, file=sys.stderr)
        log_error_line(self.container, self.config, message)
        self.last_reload = message
        self._write_state()

    # ------------------------------------------------------------------ etat
    def _write_state(self) -> None:
        health = self.engine.health
        write_engine_state(self.container.filesystem, self.container.project_root, EngineState(
            requested=self.decision.requested,
            effective="native",
            notices=self.decision.notices,
            supervisor_pid=os.getpid(),
            native_pid=self.engine.process.pid if self.engine.process else 0,
            binary_version=self.engine.binary_version,
            generation=self.engine.generation,
            connections=health.connections,
            requests=health.requests,
            rejected=health.rejected,
            restarts=self.restarts,
            extra={"security_pid": ",".join(map(str, self.security.pids))} if self.security is not None else {},
            last_reload=self.last_reload,
            updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ))


def write_python_engine_state(container: DependencyContainer, decision: EngineDecision, start_failure: str = "") -> None:
    """Etat ecrit quand le moteur Python sert (demande, ou repli signale)."""
    write_engine_state(container.filesystem, container.project_root, EngineState(
        requested=decision.requested,
        effective="python",
        reasons=decision.reasons,
        notices=decision.notices,
        supervisor_pid=os.getpid(),
        start_failure=start_failure,
        updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    ))


def python_fallback_decision(decision: EngineDecision, failure_code: str) -> EngineDecision:
    return replace(decision, effective="python", reasons=(*decision.reasons, failure_code.split(" ")[0]))
