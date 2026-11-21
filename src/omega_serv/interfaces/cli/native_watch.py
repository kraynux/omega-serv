"""Superviseur reduit du moteur natif (lot 5 memoire, 2026-11-19 ; OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §8).

`serve` en moteur natif SANS processus de securite demarre comme avant (configuration validee, instantane, natif
lance et configure, repli Python possible), puis se re-execute ici par `os.execv` : MEME PID (systemd, fichier PID,
ecran Service, administration web inchanges). Ce processus herite de la socket d'ecoute, du canal de controle et du
natif (toujours son fils), et recoit le reste par un memfd JSON (`exec_reduced_supervisor`). Il fait la meme boucle
que `serve_native.NativeSupervisor.run` - sante, etat, trafic, relance du natif, compagnons, arret - sans garder en
memoire le code de la configuration ni du serveur (mesure : ~22 Mo -> ~6 Mo).

- relance du natif : l'instantane de la generation active, gardé tel quel avec son empreinte ;
- SIGHUP : un fils ephemere (`fork`) relit la configuration et construit l'instantane avec le code complet
  (`serve_native.prepare_reload`, le meme que le superviseur complet), le rend en JSON par un tube et s'arrete ; seuls
  le resultat et ses messages restent ici. Memes refus, memes messages ;
- controle quotidien de la declaration anonyme : meme principe (fils ephemere, `DeclarationScheduler.store_says_due`) ;
- processus de securite UNIQUE (WAF, auth, proxy... ; etude §9) : lance par `serve` comme un interpreteur neuf
  (`security_entry.py`), repris ici comme le natif ; relance avec la configuration acceptee (memfd), nouveaux canaux
  confies au natif (DATA_ATTACH), SIGHUP apres chaque rechargement accepte, arrete apres le natif. Plusieurs
  processus de securite (compteurs partages, verrous herites par fork) : le superviseur complet reste.

Imports limites aux modules legers (ni dataclasses, ni typing, ni asyncio) : `test_memory_serve_imports.py` le garde."""
from __future__ import annotations

import json
import os
import select
import signal
import sys
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.services.python_command import python_module_argv

TYPE_CHECKING = False
if TYPE_CHECKING:
    import socket

    from omega_serv.infrastructure.server.native_engine import SnapshotFile

MAX_RESTARTS = 5
RESTART_WINDOW_SECONDS = 60.0
STATE_REFRESH_SECONDS = 2.0
PREPARE_TIMEOUT_SECONDS = 120.0
"""Fils ephemere du rechargement : lecture de la configuration, controles, instantane (resolution DNS des backends
comprise). Au-dela, il est arrete et le rechargement refuse."""
DUE_CHECK_TIMEOUT_SECONDS = 30.0
ENGINE_STATE_RELATIVE_PATH = Path("var") / "run" / "engine-state.json"  # = engine_state.ENGINE_STATE_RELATIVE_PATH
PID_RELATIVE_PATH = Path("var") / "run" / "omega-serv.pid"
_STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


# ---------------------------------------------------------------------------------------------- passage de relais
def exec_reduced_supervisor(payload: dict[str, object], inherited_fds: list[int]) -> str:
    """Re-execute ce processus en superviseur reduit. Ne revient qu'en cas d'echec : rend la cause, et tout est remis
    comme avant (descripteurs non heritables, signaux debloques). Les signaux d'arret et de rechargement sont bloques
    pendant le passage (le masque survit a execv) : arrives entre-temps, ils sont traites des que le superviseur reduit
    a pose ses gestionnaires - jamais l'action par defaut, qui arreterait le serveur."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        handoff_fd = os.memfd_create("omega-serv-handoff", 0)
    except OSError as e:
        return f"memfd : {e}"
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, _STOP_SIGNALS)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(handoff_fd, view):]
        os.lseek(handoff_fd, 0, os.SEEK_SET)
        for fd in (*inherited_fds, handoff_fd):
            os.set_inheritable(fd, True)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(sys.executable, python_module_argv(sys.executable, "omega_serv.interfaces.cli.native_watch",
                                                    "--handoff-fd", str(handoff_fd)))
    except OSError as e:
        failure = str(e)
    for fd in inherited_fds:
        try:
            os.set_inheritable(fd, False)
        except OSError:
            pass
    os.close(handoff_fd)
    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    return failure


def run_in_fork(task: Callable[[], object], timeout: float, close_fds: tuple[int, ...] = ()) -> object | None:
    """`task()` dans un fils ephemere (le code qu'il charge disparait avec lui) ; son resultat JSON, ou None (echec,
    delai depasse : le fils est alors arrete). Le fils ne garde ni la socket d'ecoute ni le canal de controle."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # fils
        code = 1
        try:
            os.close(read_fd)
            for sig in _STOP_SIGNALS:
                signal.signal(sig, signal.SIG_DFL)
            for fd in close_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            data = json.dumps(task(), ensure_ascii=False).encode("utf-8")
            view = memoryview(data)
            while view:
                view = view[os.write(write_fd, view):]
            code = 0
        except BaseException:  # noqa: BLE001 - un fils ne remonte jamais dans la boucle du superviseur
            import traceback
            traceback.print_exc()
        finally:
            os._exit(code)
    os.close(write_fd)
    chunks: list[bytes] = []
    deadline = time.monotonic() + timeout
    finished = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                ready, _, _ = select.select([read_fd], [], [], remaining)
            except InterruptedError:
                continue
            if not ready:
                break
            chunk = os.read(read_fd, 1 << 16)
            if not chunk:
                finished = True
                break
            chunks.append(chunk)
    finally:
        os.close(read_fd)
        if not finished:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        _, status = os.waitpid(pid, 0)
    if not finished or os.waitstatus_to_exitcode(status) != 0:
        return None
    try:
        result: object = json.loads(b"".join(chunks))
    except ValueError:
        return None
    return result


def config_memfd(config_dict: dict[str, object]) -> SnapshotFile:
    """Configuration acceptee (JSON de `OmegaServConfig.to_dict`) dans un memfd scelle, pour `security_entry.py`."""
    from omega_serv.infrastructure.server.native_engine import SnapshotFile
    from omega_serv.infrastructure.server.native_ipc import sealed_memfd
    data = json.dumps(config_dict, ensure_ascii=False).encode("utf-8")
    return SnapshotFile(sealed_memfd(data, "omega-serv-config"), len(data), b"")


def spawn_security_process(project_root: str, config_path: str, config: SnapshotFile, worker_fds: list[int]) -> int:
    """Processus de securite comme un interpreteur neuf (`security_entry.py`) ; seuls la configuration et ses canaux
    lui sont transmis (heritables le temps du lancement, comme le natif). Rend son PID."""
    argv = [*python_module_argv(sys.executable, "omega_serv.interfaces.cli.security_entry"), "--project-root", project_root,
            "--config-path", config_path, "--config-fd", str(config.fd), "--config-size", str(config.size), "--first"]
    for fd in worker_fds:
        argv += ["--data-fd", str(fd)]
    passed = [config.fd, *worker_fds]
    for fd in passed:
        os.set_inheritable(fd, True)
    try:
        return os.posix_spawn(sys.executable, argv, dict(os.environ))
    finally:
        for fd in passed:
            os.set_inheritable(fd, False)


# ---------------------------------------------------------------------------------------------- taches des fils
def _prepare_reload_task(project_root: str, config_path: str, fingerprint: object, generation: int,
                         snapshot_fd: int, config_fd: int) -> object:
    from omega_serv.interfaces.cli.serve_native import prepared_reload_payload
    assert isinstance(fingerprint, dict)
    return prepared_reload_payload(project_root, config_path, fingerprint, generation, snapshot_fd, config_fd)


def _declaration_due_task(project_root: Path) -> bool:
    from omega_serv.infrastructure.clock.system_clock import SystemClock
    from omega_serv.infrastructure.declaration.json_declaration_store import JsonDeclarationStore
    from omega_serv.interfaces.cli.declaration_scheduler import DeclarationScheduler
    return DeclarationScheduler([], JsonDeclarationStore(project_root), now=SystemClock().now).store_says_due()


# ---------------------------------------------------------------------------------------------- superviseur
class ReducedSupervisor:
    def __init__(self, handoff: dict[str, object]) -> None:
        from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
        from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
        from omega_serv.infrastructure.server.native_engine import NativeEngine, SnapshotFile
        from omega_serv.interfaces.cli.child_supervisor import ChildSupervisor, ServeCompanions
        from omega_serv.interfaces.cli.declaration_scheduler import DeclarationScheduler
        h = handoff
        self.project_root = Path(str(h["project_root"]))
        self.config_path = str(h["config_path"])
        self.listening = f"{h['bind']}:{h['port']}"
        self.listen_fd = int(str(h["listen_fd"]))
        control_fd = int(str(h["control_fd"]))
        for fd in (self.listen_fd, control_fd):
            os.set_inheritable(fd, False)  # transmis au natif seulement a sa relance, jamais aux compagnons
        self.engine = NativeEngine(Path(str(h["binary"])), self.project_root, threads=int(str(h["threads"])))
        self.engine.adopt(int(str(h["native_pid"])), control_fd, str(h["binary_version"]), int(str(h["generation"])))
        snapshot_fd = int(str(h["snapshot_fd"]))
        os.set_inheritable(snapshot_fd, False)
        self.engine.keep_snapshot = True
        self.engine.keep_snapshot_file(SnapshotFile(snapshot_fd, int(str(h["snapshot_size"])), bytes.fromhex(str(h["digest"]))))
        self.required = {str(c) for c in h["required"]}  # type: ignore[attr-defined]
        self.fingerprint = h["fingerprint"]
        self.restarts = int(str(h["restarts"]))
        self.last_reload = str(h["last_reload"])
        self._apply_settings(h)
        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()
        members: list[object] = []
        for entry in h["companions"]:  # type: ignore[attr-defined]
            if entry["kind"] == "declaration":
                members.append(DeclarationScheduler(entry["argv"], None, now=lambda: datetime.now(timezone.utc),
                                                    due=self._declaration_due))
            else:
                members.append(ChildSupervisor(entry["label"], entry["argv"]))
        self.companions = ServeCompanions(*members)
        self._traffic_file: object | None = None
        self._stop = False
        self._reload = False
        security = h.get("security")
        self.security_pid: int | None = None
        self.security_config: SnapshotFile | None = None
        self.security_restarts = 0
        self._pending_worker_fds: list[int] = []
        self._frozen = False
        if isinstance(security, dict):
            self.security_config = SnapshotFile(int(security["config_fd"]), int(security["config_size"]), b"")
            self._pending_worker_fds = [int(fd) for fd in security["worker_fds"]]
            for fd in (self.security_config.fd, *self._pending_worker_fds):
                os.set_inheritable(fd, False)

    def _apply_settings(self, values: dict[str, object]) -> None:
        self.requested = str(values["requested"])
        self.notices = [str(n) for n in values["notices"]]  # type: ignore[attr-defined]
        self.error_log = Path(str(values["error_log"]))
        self.grace = float(str(values["grace"]))

    # ------------------------------------------------------------------ journal
    def log_error(self, message: str) -> None:
        from omega_serv.domain.logging.error_log_line import format_error_log_line
        try:
            self.logger.append_line(self.error_log, format_error_log_line(datetime.now(timezone.utc), message))
        except OSError:
            pass

    # ------------------------------------------------------------------ boucle
    def run(self) -> int:
        from omega_serv.application.services.pid_file import remove_pid_file, write_pid_file
        from omega_serv.infrastructure.server.native_engine import NativeStartError
        pid_path = self.project_root / PID_RELATIVE_PATH
        write_pid_file(self.filesystem, pid_path, os.getpid())
        process = self.engine.process
        print(f"OMEGA-SERV a l'ecoute sur {self.listening} "
              f"(moteur natif {self.engine.binary_version}, PID {process.pid if process else '?'}, superviseur reduit)")
        previous = {sig: signal.signal(sig, self._on_signal) for sig in _STOP_SIGNALS}
        signal.pthread_sigmask(signal.SIG_UNBLOCK, _STOP_SIGNALS)  # bloques pendant execv (exec_reduced_supervisor)
        deaths: deque[float] = deque()
        security_deaths: deque[float] = deque()
        exit_code = 0
        if self._pending_worker_fds:  # canaux deja confies au natif par `serve` : le processus nait ici
            try:
                self.security_pid = self._fork_security(self._pending_worker_fds, [])
            except OSError as e:
                self.log_error(f"processus de securite non lance : {e}")
            finally:
                for fd in self._pending_worker_fds:
                    os.close(fd)
                self._pending_worker_fds = []
        self.companions.start()
        self._write_state()
        next_state = time.monotonic() + STATE_REFRESH_SECONDS
        try:
            while True:
                self.engine.pump(1.0)
                self._publish_native_traffic()
                self.companions.tick()
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
                    self.log_error(message)
                    if len(deaths) > MAX_RESTARTS:
                        message = (f"moteur natif arrete {len(deaths)} fois en {RESTART_WINDOW_SECONDS:.0f} s : "
                                   "arret du serveur (aucune bascule a chaud vers le moteur Python)")
                        print(message, file=sys.stderr)
                        self.log_error(message)
                        exit_code = 1
                        break
                    try:
                        self._restart_engine()
                        self.restarts += 1
                        print(f"moteur natif relance (PID {self.engine.process.pid if self.engine.process else '?'})")
                    except NativeStartError as e:
                        self.log_error(f"relance du moteur natif impossible : {e.code} : {e.detail}")
                    except OSError as e:  # processus de securite non relance
                        self.log_error(f"relance du moteur natif impossible : {e}")
                if self.security_config is not None and self.engine.alive() and not self._security_alive():
                    now = time.monotonic()
                    security_deaths.append(now)
                    while security_deaths and now - security_deaths[0] > RESTART_WINDOW_SECONDS:
                        security_deaths.popleft()
                    message = "processus de securite arrete de facon inattendue"
                    print(message, file=sys.stderr)
                    self.log_error(message)
                    if len(security_deaths) > MAX_RESTARTS:
                        message = (f"processus de securite arrete {len(security_deaths)} fois en "
                                   f"{RESTART_WINDOW_SECONDS:.0f} s : arret du serveur")
                        print(message, file=sys.stderr)
                        self.log_error(message)
                        exit_code = 1
                        break
                    try:
                        self._restart_security()
                        print(f"processus de securite relance (PID {self.security_pid})")
                    except OSError as e:
                        self.log_error(f"relance du processus de securite impossible : {e}")
                if time.monotonic() >= next_state:
                    self._write_state()
                    next_state = time.monotonic() + STATE_REFRESH_SECONDS
        finally:
            print("Arret demande - drainage des connexions en cours...")
            self.engine.stop(self.grace)
            # Lot 1 (D11) : le processus de securite vide ses connexions confiees dans le meme delai de grace.
            self._stop_security(max(5.0, self.grace + 2.0))
            self.companions.stop()
            try:
                os.close(self.listen_fd)
            except OSError:
                pass
            remove_pid_file(self.filesystem, pid_path)
            self._publish_native_traffic(stopping=True)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        return exit_code

    # ------------------------------------------------------------------ processus de securite
    def _security_alive(self) -> bool:
        if self.security_pid is None:
            return False
        try:
            pid, _status = os.waitpid(self.security_pid, os.WNOHANG)
        except ChildProcessError:
            pid = self.security_pid
        if pid == self.security_pid:
            self.security_pid = None
            return False
        return True

    def _start_security(self) -> list[socket.socket]:
        """Nouveau processus de securite, un canal par fil natif ; rend les extremites « natif » (a fermer)."""
        from omega_serv.infrastructure.server.native_ipc import data_channel_pair
        pairs = [data_channel_pair() for _ in range(max(1, self.engine.threads))]
        try:
            self.security_pid = self._fork_security([worker_end.fileno() for _native_end, worker_end in pairs],
                                                    [native_end.fileno() for native_end, _worker_end in pairs])
        except OSError:
            for native_end, _worker_end in pairs:
                native_end.close()
            raise
        finally:
            for _native_end, worker_end in pairs:
                worker_end.close()
        return [native_end for native_end, _worker_end in pairs]

    def _fork_security(self, worker_fds: list[int], close_in_child: list[int]) -> int:
        """Etude §11 : processus de securite ne de ce superviseur (fork apres gc.freeze) - pages de l'interpreteur
        partagees au lieu d'un interpreteur neuf (-2,4 Mo mesures). Il recoit la configuration acceptee (memfd) et
        construit ensuite son serveur comme `security_entry.py`."""
        import gc
        config = self.security_config
        assert config is not None
        if not self._frozen:
            gc.collect()
            gc.freeze()  # objets deja la : jamais parcourus par le ramasse-miettes du fils, pages laissees partagees
            self._frozen = True
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid:
            return pid
        code = 1
        try:
            signal.pthread_sigmask(signal.SIG_BLOCK, _STOP_SIGNALS)  # jusqu'aux gestionnaires (security_worker)
            for sig in _STOP_SIGNALS:
                signal.signal(sig, signal.SIG_DFL)
            try:  # ps / top : nom distinct du superviseur (meme ligne de commande, fork)
                with open("/proc/self/comm", "w", encoding="ascii") as comm:
                    comm.write("omega-securite")
            except OSError:
                pass
            snapshot = self.engine.active_snapshot
            for fd in (self.listen_fd, self.engine.control_fd(), snapshot.fd if snapshot else -1, *close_in_child):
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            text = os.pread(config.fd, config.size, 0)
            from omega_serv.infrastructure.process.lazy_ssl import defer_ssl_import
            defer_ssl_import()
            from omega_serv.interfaces.cli.security_entry import serve_accepted_config
            code = serve_accepted_config(str(self.project_root), self.config_path, text, worker_fds)
        except BaseException:  # noqa: BLE001 - un fils ne remonte jamais dans la boucle du superviseur
            import traceback
            traceback.print_exc()
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)

    def _stop_security(self, timeout: float) -> None:
        if self.security_pid is None:
            return
        try:
            os.kill(self.security_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + timeout
        while self._security_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.security_pid is not None:
            try:
                os.kill(self.security_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            while self._security_alive():
                time.sleep(0.05)

    def _restart_security(self) -> None:
        """Processus de securite arrete, natif vivant : nouveaux canaux confies au natif (DATA_ATTACH)."""
        channels = self._start_security()
        try:
            for index, channel in enumerate(channels):
                self.engine.attach_data_channel(index, channel.fileno())
        finally:
            for channel in channels:
                channel.close()
        self.security_restarts += 1

    def _restart_engine(self) -> None:
        """Natif relance avec l'instantane de la generation active ; un processus de securite est relance avec lui
        (l'ancien n'a plus de canal valide), comme NativeSupervisor._start_engine."""
        from omega_serv.infrastructure.server.native_engine import NativeStartError
        snapshot = self.engine.active_snapshot
        assert snapshot is not None
        channels: list[socket.socket] = []
        if self.security_config is not None:
            self._stop_security(5.0)
            channels = self._start_security()
        try:
            self.engine.start_with_file(self.required, snapshot, self.engine.generation, [self.listen_fd],
                                        [channel.fileno() for channel in channels])
        except NativeStartError:
            self._stop_security(5.0)
            raise
        finally:
            for channel in channels:
                channel.close()

    def _on_signal(self, signum: int, _frame: object) -> None:
        if signum == signal.SIGHUP:
            self._reload = True
        else:
            self._stop = True

    def _child_close_fds(self) -> tuple[int, ...]:
        return (self.listen_fd, self.engine.control_fd())

    # ------------------------------------------------------------------ rechargement
    def _handle_reload(self) -> None:
        print("Rechargement demande (SIGHUP) - moteur natif...")
        self.companions.reload()
        generation = self.engine.generation + 1
        root, config_path, fingerprint = str(self.project_root), self.config_path, self.fingerprint
        from omega_serv.infrastructure.server.native_engine import SnapshotFile
        from omega_serv.infrastructure.server.native_ipc import new_snapshot_memfd
        try:
            snapshot_fd = new_snapshot_memfd()
            config_fd = new_snapshot_memfd("omega-serv-config")
        except OSError as e:
            self._refuse(f"memfd : {e}")
            return
        outcome = run_in_fork(
            lambda: _prepare_reload_task(root, config_path, fingerprint, generation, snapshot_fd, config_fd),
            PREPARE_TIMEOUT_SECONDS, self._child_close_fds())
        snapshot = SnapshotFile(snapshot_fd, 0, b"")
        config = SnapshotFile(config_fd, 0, b"")
        if not isinstance(outcome, dict) or not outcome.get("ok"):
            snapshot.close()
            config.close()
            if isinstance(outcome, dict):
                self._refuse(str(outcome.get("reason", "")))
            else:
                self._refuse("preparation de la nouvelle configuration impossible (voir les messages ci-dessus)")
            return
        for note in outcome["notes"]:  # lot 6 : resolution DNS des backends
            self.log_error(str(note))
        snapshot.size = int(str(outcome["size"]))
        snapshot.digest = bytes.fromhex(str(outcome["digest"]))
        error = self.engine.reload_with(lambda: self.engine.apply_snapshot_file(snapshot, generation))
        if error is not None:
            snapshot.close()
            config.close()
            self._refuse(f"configuration refusee par le moteur natif : {error}")
            return
        self.engine.keep_snapshot_file(snapshot)
        if self.security_config is not None:
            if self.security_pid is not None:
                try:
                    os.kill(self.security_pid, signal.SIGHUP)  # regles WAF, zones Auth... relues comme par Python
                except ProcessLookupError:
                    pass
            self.security_config.close()
            config.size = int(str(outcome["config_size"]))
            self.security_config = config  # relance future : la configuration qui vient d'etre acceptee
        else:
            config.close()
        self.fingerprint = outcome["fingerprint"]
        self._apply_settings(outcome)
        for warning in outcome["warnings"]:  # lot 8 (C15) : comme au demarrage
            self.log_error(str(warning))
        self.last_reload = f"generation {self.engine.generation} active"
        print(f"Rechargement termine (generation {self.engine.generation}).")
        self._write_state()

    def _refuse(self, reason: str) -> None:
        message = f"Rechargement REFUSE - la configuration precedente reste active : {reason}"
        print(message, file=sys.stderr)
        self.log_error(message)
        self.last_reload = message
        self._write_state()

    def _declaration_due(self) -> bool:
        root = self.project_root
        return run_in_fork(lambda: _declaration_due_task(root), DUE_CHECK_TIMEOUT_SECONDS,
                           self._child_close_fds()) is True

    # ------------------------------------------------------------------ etat
    def _publish_native_traffic(self, *, stopping: bool = False) -> None:
        """Comme NativeSupervisor._publish_native_traffic (lot 9b)."""
        from omega_serv.infrastructure.server.traffic_meter import TrafficFile
        process = self.engine.process
        pid = process.pid if process is not None and not stopping else 0
        traffic = self._traffic_file
        if isinstance(traffic, TrafficFile) and traffic.pid != pid:
            traffic.remove()
            traffic = self._traffic_file = None
        health = self.engine.health
        if not pid or health.bytes_in is None or health.bytes_out is None:
            return
        if not isinstance(traffic, TrafficFile):
            traffic = self._traffic_file = TrafficFile(self.project_root, pid)
        traffic.publish(health.bytes_in, health.bytes_out)

    def state_payload(self) -> dict[str, object]:
        """Memes cles, meme ordre que `engine_state.EngineState` (asdict) : lu par l'ecran Etat et `engine status`."""
        health = self.engine.health
        process = self.engine.process
        return {
            "requested": self.requested,
            "effective": "native",
            "reasons": [],
            "notices": list(self.notices),
            "supervisor_pid": os.getpid(),
            "native_pid": process.pid if process else 0,
            "binary_version": self.engine.binary_version,
            "generation": self.engine.generation,
            "connections": health.connections,
            "requests": health.requests,
            "rejected": health.rejected,
            "restarts": self.restarts,
            "last_reload": self.last_reload,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "start_failure": "",
            "extra": {**({"security_pid": str(self.security_pid or "")} if self.security_config is not None else {}),
                      "proxy_relayed": str(health.proxy_relayed),
                      "proxy_pending_body": str(health.proxy_pending_body),
                      "proxy_inspections": str(health.proxy_inspections),
                      "upstream_connections": str(health.upstream_connections),
                      "upstream_retries": str(health.upstream_retries),
                      "upstream_idle": str(health.upstream_idle)},
        }

    def _write_state(self) -> None:
        try:
            self.filesystem.atomic_write_text(self.project_root / ENGINE_STATE_RELATIVE_PATH,
                                              json.dumps(self.state_payload(), ensure_ascii=False, indent=1))
        except OSError:
            pass  # information d'affichage : jamais une cause d'arret du serveur


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    handoff_fd = int(args[args.index("--handoff-fd") + 1])
    with os.fdopen(handoff_fd, "rb") as handoff:
        payload = json.loads(handoff.read())
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]  # journalctl, comme `serve`
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    return ReducedSupervisor(payload).run()


if __name__ == "__main__":
    sys.exit(main())
