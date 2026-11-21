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
  confies au natif par DATA_ATTACH), recharge sur SIGHUP, arrete avec le natif ;
- lot 5 memoire (2026-11-19, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §8) : sans processus de securite, une fois le
  natif lance et configure, ce superviseur se re-execute (MEME PID) en superviseur reduit (`native_watch.py`), qui
  fait la meme boucle sans garder en memoire le code de la configuration ; le rechargement y est prepare par
  `prepare_reload`, le meme que celui d'ici."""
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
from typing import TYPE_CHECKING

from omega_serv.application.server.engine_selection import (
    NATIVE_BINARY_RELATIVE_PATH,
    EngineDecision,
    decide_engine,
    log_reason,
    proxy_engine_problems,
)
from omega_serv.application.server.engine_state import EngineState, write_engine_state
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.logging.error_log_line import format_error_log_line

if TYPE_CHECKING:
    from omega_serv.infrastructure.server.traffic_meter import TrafficFile
    from omega_serv.infrastructure.waf.shared_counters import SharedCounters

from omega_serv.interfaces.cli.native_watch import (  # memes regles dans les deux superviseurs
    MAX_RESTARTS,
    RESTART_WINDOW_SECONDS,
    STATE_REFRESH_SECONDS,
)


def native_binary_path(container: DependencyContainer) -> Path:
    return container.project_root / NATIVE_BINARY_RELATIVE_PATH


def current_decision(config: OmegaServConfig, container: DependencyContainer) -> EngineDecision:
    from omega_serv.infrastructure.process.native_engine_process import native_binary_problem
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


def _preload_security_code(config: OmegaServConfig) -> None:
    """Code du processus de securite charge par le superviseur juste AVANT le fork : ses pages restent partagees
    (mesure du 2026-11-19 : charge apres le fork, natif + WAF passait de 41 a 47 Mo). Sans processus de securite
    (natif seul), le superviseur ne le charge jamais : ni asyncio ni le serveur Python (7 Mo de moins)."""
    from omega_serv.application.server.option_code import preload_server_code

    preload_server_code(config, "omega_serv.infrastructure.server.security_worker")


class SecurityProcess:
    """Processus Python de securite (lot 4) : `fork` du superviseur (mono-fil), qui construit SON serveur Python
    (`build_server`, aucun port ecoute) et sert les INSPECT de tous les fils du natif."""

    def __init__(self, container: DependencyContainer, config_path: Path, counters: SharedCounters | None = None) -> None:
        self.container = container
        self.config_path = config_path
        self.counters = counters  # plusieurs processus de securite : compteurs partages (rate limit, reputation), comme le mode boost
        self.pid: int | None = None
        self.first = False  # lot 6 (P6) : processus n° 0 (fil natif 0, administration, sondes des zones natives)
        self.spawned = False
        self.deferred = False
        """Etude §11 : au demarrage, seulement les canaux ; le superviseur reduit fait naitre le processus par fork
        (pages de l'interpreteur partagees, -2,4 Mo mesures). Repli : `launch_deferred` (interpreteur neuf)."""
        self.pending_worker_ends: list[socket.socket] = []
        """Lot 5 (suite) : interpreteur neuf (`security_entry.py`) au lieu d'un fork, quand le superviseur va se
        reduire - un fork garderait tout ce que le superviseur complet a charge (CLI, validation...)."""

    def start(self, config: OmegaServConfig, channels: int, close_in_child: list[int]) -> list[socket.socket]:
        """Rend les extremites « natif » des canaux (a transmettre puis fermer par l'appelant)."""
        from omega_serv.infrastructure.server.native_ipc import data_channel_pair
        if self.spawned:
            if self.deferred:
                return self._open_deferred(channels)
            return self._start_spawned(config, channels)
        _preload_security_code(config)
        pairs = [data_channel_pair() for _ in range(channels)]  # correctif 2.6.2 (D20) : tampons agrandis
        pid = os.fork()
        if pid == 0:  # processus de securite
            code = 1
            try:
                signal.pthread_sigmask(signal.SIG_BLOCK, _SECURITY_STARTUP_SIGNALS)  # voir security_worker
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

    def _open_deferred(self, channels: int) -> list[socket.socket]:
        from omega_serv.infrastructure.server.native_ipc import data_channel_pair
        self.close_pending()
        pairs = [data_channel_pair() for _ in range(channels)]
        self.pending_worker_ends = [worker_end for _native_end, worker_end in pairs]
        return [native_end for native_end, _worker_end in pairs]

    def close_pending(self) -> None:
        for end in self.pending_worker_ends:
            end.close()
        self.pending_worker_ends = []

    def launch_deferred(self, config: OmegaServConfig) -> None:
        """Superviseur reduit non lance : processus de securite lance ici, sur les canaux deja confies au natif."""
        from omega_serv.interfaces.cli.native_watch import config_memfd, spawn_security_process
        self.deferred = False
        if not self.pending_worker_ends:
            return
        config_file = config_memfd(config.to_dict())
        try:
            self.pid = spawn_security_process(str(self.container.project_root), str(self.config_path), config_file,
                                              [end.fileno() for end in self.pending_worker_ends])
        finally:
            config_file.close()
            self.close_pending()

    def _start_spawned(self, config: OmegaServConfig, channels: int) -> list[socket.socket]:
        from omega_serv.infrastructure.server.native_ipc import data_channel_pair
        from omega_serv.interfaces.cli.native_watch import config_memfd, spawn_security_process
        pairs = [data_channel_pair() for _ in range(channels)]
        config_file = config_memfd(config.to_dict())
        try:
            self.pid = spawn_security_process(str(self.container.project_root), str(self.config_path), config_file,
                                              [worker_end.fileno() for _native_end, worker_end in pairs])
        except OSError:
            for native_end, _worker_end in pairs:
                native_end.close()
            raise
        finally:
            config_file.close()
            for _native_end, worker_end in pairs:
                worker_end.close()
        return [native_end for native_end, _worker_end in pairs]

    def _serve(self, config: OmegaServConfig, channel_fds: list[int]) -> int:
        return serve_security(self.container, self.config_path, config, channel_fds, self.counters, self.first)

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
        self.close_pending()
        self.signal(signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while self.alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.alive():
            self.signal(signal.SIGKILL)
            while self.alive():
                time.sleep(0.05)


def serve_security(container: DependencyContainer, config_path: Path, config: OmegaServConfig, channel_fds: list[int],
                   counters: SharedCounters | None, first: bool) -> int:
    """Corps du processus de securite (fork du superviseur, ou interpreteur neuf : security_entry.py)."""
    from omega_serv.application.config.load_config import load_config
    from omega_serv.application.server.start_server import build_server, try_reload_server
    from omega_serv.infrastructure.server.security_worker import run_security_worker
    server = build_server(config, container.project_root, container.filesystem, container.logger, container.clock,
                          shared_counters=counters)

    def reload() -> None:
        result = load_config(container.configuration, config_path)
        if not result.success or result.config is None:
            print("processus de securite : rechargement refuse (configuration invalide)", file=sys.stderr)
            return
        error = try_reload_server(server, result.config, container.project_root, container.filesystem, container.clock)
        if error is not None:
            print(f"processus de securite : rechargement REFUSE - regles precedentes actives : {error}", file=sys.stderr)

    return run_security_worker(server, channel_fds, reload, first=first)


class SecurityPool:
    """Lot 7 : N processus de securite. Le fil natif i est servi par le processus i % N ; les
    compteurs (rate limit, reputation) sont partages entre eux par le MEME mecanisme que le mode boost
    (SharedCounters, memoire partagee + verrous herites par fork)."""

    def __init__(self, container: DependencyContainer, config_path: Path, processes: int, counters: SharedCounters | None) -> None:
        self.members = [SecurityProcess(container, config_path, counters) for _ in range(max(1, processes))]
        self.members[0].first = True  # lot 6 (P6) : sert le fil 0, donc l'administration ; sonde les zones natives

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


def reload_fingerprint(config: OmegaServConfig) -> dict[str, object]:
    """Ce qu'un rechargement a chaud ne peut pas changer avec le natif, sous une forme JSON : le superviseur reduit
    (lot 5) le garde a la place de la configuration et le compare a celui de la nouvelle."""
    from omega_serv.infrastructure.server.native_snapshot import inspect_section
    return {
        "server.bind": config.server.bind,
        "server.port": config.server.port,
        "server.listen_backlog": config.server.listen_backlog,
        "tls": repr(config.tls),  # certificat, cle, versions : charges une fois au demarrage, comme Python
        "server.workers": config.server.workers,  # nombre de processus de securite
        # lot 4 : le processus de securite et ses canaux existent ou non des le demarrage
        "security_process": inspect_section(config) is not None,
        "security_options": {name: config.option_enabled(name) for name in _SECURITY_PROCESS_OPTIONS},
    }


def restart_blocker(old: dict[str, object], new: dict[str, object]) -> str | None:
    """Socket et TLS fixes au demarrage : le premier element modifie, None si rien."""
    for label in ("server.bind", "server.port", "server.listen_backlog", "tls", "server.workers"):
        if old.get(label) != new.get(label):
            return label
    if old.get("security_process") != new.get("security_process"):
        before = old.get("security_options") or {}
        after = new.get("security_options") or {}
        assert isinstance(before, dict) and isinstance(after, dict)
        return _security_process_label_from([name for name in _SECURITY_PROCESS_OPTIONS
                                             if bool(before.get(name)) != bool(after.get(name))])
    return None


def _restart_blocker(old: OmegaServConfig, new: OmegaServConfig) -> str | None:
    return restart_blocker(reload_fingerprint(old), reload_fingerprint(new))


_SECURITY_STARTUP_SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
"""= security_worker.STARTUP_SIGNALS (module lourd) : bloques jusqu'aux gestionnaires du processus de securite."""

# Options qui font exister le processus de securite (native_snapshot.inspect_section).
_SECURITY_PROCESS_OPTIONS = ("reverse_proxy", "fastcgi", "upload", "dirlisting", "trusted_proxy", "waf", "auth",
                             "active_defense")


def _security_process_label(old: OmegaServConfig, new: OmegaServConfig) -> str:
    """Plan proxy natif v2, lot A (D15, E8) : nommer l'option qui demande le redemarrage - avant, toujours
    « leurres / WAF / Active Defense / Auth », meme quand c'etait le reverse proxy qu'on activait."""
    return _security_process_label_from([name for name in _SECURITY_PROCESS_OPTIONS
                                         if old.option_enabled(name) != new.option_enabled(name)])


def _security_process_label_from(changed_options: list[str]) -> str:
    names = ", ".join(f"options.{name}" for name in changed_options) or "options de securite"
    return f"{names} (le processus de securite du moteur natif n'existe que s'il est lance au demarrage)"


class PreparedReload:
    """Nouvelle generation acceptee par les controles de `prepare_reload`, pas encore envoyee au natif."""

    def __init__(self, config: OmegaServConfig, decision: EngineDecision, snapshot: bytes, notes: list[str],
                 warnings: list[str]) -> None:
        self.config = config
        self.decision = decision
        self.snapshot = snapshot
        self.notes = notes
        """Lignes d'error.log de la construction de l'instantane (adresses des noms DNS des backends, lot 6)."""
        self.warnings = warnings
        """Avertissements a ecrire si le natif accepte (TLS amont non verifie, lot 8 C15)."""


def prepare_reload(container: DependencyContainer, config_path: Path, old_fingerprint: dict[str, object],
                   generation: int, security_processes: int) -> PreparedReload | str:
    """Relit et controle la configuration, construit l'instantane : PreparedReload, ou la raison du refus (texte du
    journal). Commun au superviseur complet et au superviseur reduit (lot 5, dans un fils ephemere)."""
    from omega_serv.application.config.load_config import load_config
    from omega_serv.application.config.validate_config import unverified_upstream_tls_warnings
    from omega_serv.infrastructure.server.native_engine import snapshot_bytes
    result = load_config(container.configuration, config_path)
    if not result.success or result.config is None:
        return "configuration invalide : " + "; ".join(result.errors)
    new = result.config
    refused = proxy_engine_problems(new).errors  # plan proxy natif v2, lot 3 (P8) : meme refus qu'au demarrage
    if refused:
        return "; ".join(problem.log_text for problem in refused)
    decision = current_decision(new, container)
    if decision.effective != "native":
        causes = ", ".join(log_reason(r) for r in decision.reasons) or "moteur python demande"
        return f"la nouvelle configuration exige le moteur Python ({causes}) - redemarrage complet necessaire"
    blocker = restart_blocker(old_fingerprint, reload_fingerprint(new))
    if blocker is not None:
        return f"{blocker} modifie - redemarrage complet necessaire"
    notes: list[str] = []
    snapshot = snapshot_bytes(new, container.project_root, generation, security_processes, notes)
    return PreparedReload(new, decision, snapshot, notes,
                          [f"avertissement : {w.log_text}" for w in unverified_upstream_tls_warnings(new)])


def prepared_reload_payload(project_root: str, config_path: str, old_fingerprint: dict[str, object],
                            generation: int, snapshot_fd: int, config_fd: int) -> dict[str, object]:
    """Superviseur reduit (lot 5) : `prepare_reload` dans le fils ephemere ; l'instantane est ecrit et scelle dans
    `snapshot_fd`, la configuration acceptee (pour relancer un processus de securite) dans `config_fd` - deux memfd
    crees par le superviseur ; le reste rendu en JSON."""
    import json

    from omega_serv.infrastructure.server.native_ipc import fill_and_seal, snapshot_digest
    container = DependencyContainer(Path(project_root))
    outcome = prepare_reload(container, Path(config_path), old_fingerprint, generation, 1)
    if isinstance(outcome, str):
        return {"ok": False, "reason": outcome}
    fill_and_seal(snapshot_fd, outcome.snapshot)
    config_text = json.dumps(outcome.config.to_dict(), ensure_ascii=False).encode("utf-8")
    fill_and_seal(config_fd, config_text)
    return {"ok": True, "size": len(outcome.snapshot), "config_size": len(config_text),
            "digest": snapshot_digest(outcome.snapshot).hex(),
            "notes": outcome.notes, "warnings": outcome.warnings, "fingerprint": reload_fingerprint(outcome.config),
            **_watch_settings(container, outcome.config, outcome.decision)}


def _watch_settings(container: DependencyContainer, config: OmegaServConfig, decision: EngineDecision) -> dict[str, object]:
    """Ce que le superviseur reduit retient d'une configuration acceptee."""
    return {"requested": decision.requested, "notices": list(decision.notices),
            "error_log": str(container.project_root / config.logs.error),
            "grace": float(config.server.shutdown_grace_period_seconds)}


class NativeSupervisor:
    def __init__(self, config: OmegaServConfig, config_path: Path, container: DependencyContainer,
                 decision: EngineDecision, riposte: object | None, reduce: bool = False) -> None:
        """`reduce` (lot 5) : `reduce()` suivra `start()` ; un processus de securite unique est alors lance comme un
        interpreteur neuf, que le superviseur reduit reprendra."""
        from omega_serv.core.platform_info import cpu_info
        from omega_serv.infrastructure.server.native_engine import NativeEngine
        from omega_serv.infrastructure.server.native_snapshot import inspect_section
        from omega_serv.infrastructure.waf.shared_counters import SharedCounters
        from omega_serv.interfaces.cli.serve_workers import effective_worker_count
        self.config = config
        self.config_path = config_path
        self.container = container
        self.decision = decision
        self.riposte = riposte
        self.threads = native_thread_count()
        self.engine = NativeEngine(native_binary_path(container), container.project_root, threads=self.threads)
        # Plan proxy natif v2, lot 6 (C18) : adresses des noms DNS des backends, ecrites dans error.log.
        self.engine.notes_sink = lambda message: log_error_line(self.container, self.config, message)
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
        self._traffic_file: TrafficFile | None = None
        """Lot 9b (tableau de bord web) : trafic du natif, publie sous le PID du natif."""
        self.security: SecurityPool | None = None
        if inspect_section(config) is not None:
            if self.security_processes > 1:
                self.counters = SharedCounters.create(f"omega_serv_{config.server.port}")
            self.security = SecurityPool(container, config_path, self.security_processes, self.counters)
            # Plusieurs processus : verrous des compteurs partages herites par fork - superviseur complet garde.
            self.security.members[0].spawned = reduce and self.security_processes == 1
            self.security.members[0].deferred = reduce and self.security_processes == 1
            self.engine.security_processes = self.security_processes  # lot 3 (P6) : /.omega-serv-admin/ -> n° 0
        # Lot 5 : instantane garde (memfd) pour le superviseur reduit, seulement s'il va prendre le relais.
        self.engine.keep_snapshot = reduce and (self.security is None or self.security_processes == 1)
        self.security_restarts = 0
        self.listen_socket: socket.socket | None = None
        self.restarts = 0
        self.last_reload = ""
        self._stop = False
        self._reload = False

    # ------------------------------------------------------------------ demarrage
    def start(self) -> str | None:
        """None si le natif sert ; sinon la cause (natif arrete, socket fermee : repli Python possible)."""
        from omega_serv.infrastructure.server.native_engine import NativeStartError
        from omega_serv.interfaces.cli.serve_workers import open_listen_socket
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
        from omega_serv.infrastructure.server.native_engine import NativeStartError
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

    # ------------------------------------------------------------------ superviseur reduit (lot 5)
    def reduce(self) -> str | None:
        """Voir `_reduce`. Sans re-execution, un processus de securite differe est lance ici (interpreteur neuf,
        sur les canaux deja confies au natif) : jamais un natif sans processus de securite."""
        failure = self._reduce()
        if self.security is not None and self.security.members[0].pending_worker_ends:
            self.security.members[0].launch_deferred(self.config)
        return failure

    def _reduce(self) -> str | None:
        """Re-execution en superviseur reduit (meme PID), qui reprend le natif, la socket, le canal de controle, le
        processus de securite s'il existe, et lance les compagnons. Ne revient qu'en cas d'echec (cause rendue) : ce
        superviseur continue alors. None sans rien faire avec plusieurs processus de securite (compteurs partages)."""
        from omega_serv.infrastructure.server.native_engine import required_capabilities
        from omega_serv.interfaces.cli.native_watch import exec_reduced_supervisor
        process = self.engine.process
        snapshot = self.engine.active_snapshot
        if self.listen_socket is None or process is None or snapshot is None:
            return None
        security_payload: dict[str, object] | None = None
        inherited = [self.listen_socket.fileno(), self.engine.control_fd(), snapshot.fd]
        if self.security is not None:
            member = self.security.members[0]
            if len(self.security.members) != 1 or not member.pending_worker_ends:
                return None
            from omega_serv.interfaces.cli.native_watch import config_memfd
            config_file = config_memfd(self.config.to_dict())
            worker_fds = [end.fileno() for end in member.pending_worker_ends]
            security_payload = {"config_fd": config_file.fd, "config_size": config_file.size, "worker_fds": worker_fds}
            inherited += [config_file.fd, *worker_fds]
        payload = {
            "project_root": str(self.container.project_root),
            "config_path": str(self.config_path),
            "bind": self.config.server.bind,
            "port": self.config.server.port,
            "listen_fd": self.listen_socket.fileno(),
            "control_fd": self.engine.control_fd(),
            "native_pid": process.pid,
            "binary": str(self.engine.binary),
            "binary_version": self.engine.binary_version,
            "threads": self.threads,
            "generation": self.engine.generation,
            "required": sorted(required_capabilities(self.config)),
            "snapshot_fd": snapshot.fd,
            "snapshot_size": snapshot.size,
            "digest": snapshot.digest.hex(),
            "fingerprint": reload_fingerprint(self.config),
            "restarts": self.restarts,
            "last_reload": self.last_reload,
            "companions": self.riposte.handoff() if self.riposte is not None else [],  # type: ignore[attr-defined]
            "security": security_payload,
            **_watch_settings(self.container, self.config, self.decision),
        }
        failure = exec_reduced_supervisor(payload, inherited)
        if security_payload is not None:
            os.close(int(str(security_payload["config_fd"])))
        message = f"superviseur reduit du moteur natif non lance ({failure}) - superviseur complet garde"
        print(message, file=sys.stderr)
        log_error_line(self.container, self.config, message)
        return failure

    # ------------------------------------------------------------------ boucle
    def run(self) -> int:
        from omega_serv.application.services.pid_file import remove_pid_file, write_pid_file
        from omega_serv.infrastructure.server.native_engine import NativeStartError
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
                self._publish_native_traffic()
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
                # Lot 1 (D11) : le processus de securite vide ses connexions confiees dans le meme delai de grace.
                self.security.stop(max(5.0, self.config.server.shutdown_grace_period_seconds + 2.0))
            if self.counters is not None:
                self.counters.destroy()
            if self.riposte is not None:
                self.riposte.stop()  # type: ignore[attr-defined]
            if self.listen_socket is not None:
                self.listen_socket.close()
            remove_pid_file(container.filesystem, pid_path)
            self._publish_native_traffic(stopping=True)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        return exit_code

    def _publish_native_traffic(self, *, stopping: bool = False) -> None:
        """Lot 9b : octets recus et envoyes par le natif (trame HEALTH), dans var/run/traffic/<PID du natif>.json ;
        le processus d'administration les additionne a ceux des processus Python. Natif relance : nouveau fichier."""
        from omega_serv.infrastructure.server.traffic_meter import TrafficFile
        process = self.engine.process
        pid = process.pid if process is not None and not stopping else 0
        if self._traffic_file is not None and self._traffic_file.pid != pid:
            self._traffic_file.remove()
            self._traffic_file = None
        health = self.engine.health
        if not pid or health.bytes_in is None or health.bytes_out is None:
            return
        if self._traffic_file is None:
            self._traffic_file = TrafficFile(self.container.project_root, pid)
        self._traffic_file.publish(health.bytes_in, health.bytes_out)

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
        generation = self.engine.generation + 1
        outcome = prepare_reload(self.container, self.config_path, reload_fingerprint(self.config), generation,
                                 self.engine.security_processes)
        if isinstance(outcome, str):
            self._refuse(outcome)
            return
        for note in outcome.notes:  # lot 6 : resolution DNS des backends
            log_error_line(self.container, self.config, note)
        error = self.engine.reload_with(lambda: self.engine.apply_snapshot(outcome.snapshot, None, generation))
        if error is not None:
            self._refuse(f"configuration refusee par le moteur natif : {error}")
            return
        if self.security is not None:
            self.security.signal(signal.SIGHUP)  # regles WAF, zones Auth... relues comme par le moteur Python
        self.config = outcome.config
        self.decision = outcome.decision
        for warning in outcome.warnings:  # lot 8 (C15) : comme au demarrage
            log_error_line(self.container, self.config, warning)
        self.last_reload = f"generation {self.engine.generation} active"
        print(f"Rechargement termine (generation {self.engine.generation}).")
        self._write_state()

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
            extra={**({"security_pid": ",".join(map(str, self.security.pids))} if self.security is not None else {}),
                   # Plan proxy natif v2, lot 4 : relais natif (cumul et budgets en cours d'usage, C2)
                   "proxy_relayed": str(health.proxy_relayed),
                   "proxy_pending_body": str(health.proxy_pending_body),
                   "proxy_inspections": str(health.proxy_inspections),
                   "upstream_connections": str(health.upstream_connections),
                   # Lot 5 : pool et nouveaux essais
                   "upstream_retries": str(health.upstream_retries),
                   "upstream_idle": str(health.upstream_idle)},
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
