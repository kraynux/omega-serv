"""Pilote du moteur natif omega-http-core cote superviseur (plan moteur C++ lot 3 ; contrat IPC §1-6).

Le superviseur ouvre la socket d'ecoute UNE fois et la confie a un seul moteur (§16.5) : ce module lance le
natif avec elle, verifie la poignee de main (version de contrat, capacites), envoie la configuration par
generation (instantane construit par les VRAIES fonctions Python, native_snapshot.py) et attend son
acquittement. Tout echec AVANT le premier acquittement leve `NativeStartError` : le natif est arrete et la
socket reste au superviseur, qui la donne au moteur Python (repli au demarrage, plan §6) - jamais deux moteurs
sur le port, jamais un natif partiellement configure."""
from __future__ import annotations

import os
import select
import socket
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from omega_serv.infrastructure.process.native_engine_process import NativeEngineProcess
from omega_serv.infrastructure.server import native_ipc as ipc

TYPE_CHECKING = False  # lot 5 (2026-11-19) : module charge par le superviseur reduit, sans typing ni dataclasses
if TYPE_CHECKING:
    from omega_serv.domain.config.entities import OmegaServConfig

HELLO_TIMEOUT_SECONDS = 5.0  # contrat §5
CONFIG_ACK_TIMEOUT_SECONDS = 15.0

# Codes de cause d'un repli au demarrage (fichier d'etat, ecran Etat, journal).
EXITED = "native_exited"
NO_HELLO = "native_no_hello"
CONTRACT_MISMATCH = "native_contract_mismatch"
CAPABILITIES_MISSING = "native_capabilities_missing"
CONFIG_REFUSED = "native_config_refused"
CHANNEL_ERROR = "native_channel_error"


class NativeStartError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code} : {detail}")
        self.code = code
        self.detail = detail


def required_capabilities(config: OmegaServConfig) -> set[str]:
    """Ce que la configuration exige du binaire (contrat §3.1) ; comparees a celles annoncees dans HELLO."""
    from omega_serv.application.server.engine_selection import decide_proxy_zones
    needed = {"static", "range", "precompressed", "access_log"}
    if config.security.security_headers_enabled:
        needed.add("security_headers")
    if config.tls.enabled and config.tls.mode == "direct":
        needed.add("tls")
    for option, capability in (("redirects", "redirects"), ("rewrites", "rewrites"), ("aliases", "aliases"),
                               ("access_control", "access_rules"), ("trusted_proxy", "trusted_proxy")):
        if config.option_enabled(option):
            needed.add(capability)
    # Plan proxy natif v2, lot 4 : connexion rendue par Python (HANDOFF_DONE) des qu'une route peut etre confiee - un
    # binaire plus ancien la perdrait ; relais natif des qu'une zone est relayee par le natif.
    if any(config.option_enabled(option) for option in ("reverse_proxy", "fastcgi", "upload")):
        needed.add("handoff_done")
    if any(zone.engine == "native" for zone in decide_proxy_zones(config)):
        needed.add("proxy_relay")
        needed.add("proxy_stream")  # lot 5 : chunked, fin par la fermeture, flux, pool - un binaire du lot 4 les refuse
        needed.add("proxy_balance")  # lot 6 : plusieurs backends, sante partagee, noms DNS, etats du processus n° 0
    if any(zone.engine == "native" and _zone_uses_upstream_tls(config, zone.url_prefix)
           for zone in decide_proxy_zones(config)):
        needed.add("proxy_tls")  # lot 8 : TLS vers le backend - un binaire plus ancien ne sait pas le faire
    if any(zone.engine == "native" and _zone_uses_websocket(config, zone.url_prefix)
           for zone in decide_proxy_zones(config)):
        needed.add("proxy_websocket")  # lot 10 : tunnel WebSocket natif - un binaire plus ancien le confierait mal
    if needed & {"tls", "proxy_relay"} == {"tls", "proxy_relay"}:
        needed.add("proxy_tls_direct")  # lot 9 : relais sous TLS direct (administration vers le fil 0 comprise)
    return needed


def _zone_uses_upstream_tls(config: OmegaServConfig, url_prefix: str) -> bool:
    from omega_serv.domain.routing.proxy_zone import parse_proxy_zones
    zones = parse_proxy_zones(config.options["reverse_proxy"].settings.get("zones", []))
    return any(u.use_tls for zone in zones if zone.url_prefix == url_prefix for u in zone.upstreams)


def _zone_uses_websocket(config: OmegaServConfig, url_prefix: str) -> bool:
    from omega_serv.domain.routing.proxy_zone import parse_proxy_zones
    zones = parse_proxy_zones(config.options["reverse_proxy"].settings.get("zones", []))
    return any(zone.websocket_enabled for zone in zones if zone.url_prefix == url_prefix)


def snapshot_bytes(config: OmegaServConfig, project_root: Path, generation: int, security_processes: int,
                   notes: list[str]) -> bytes:
    """Instantane JSON envoye au natif (construit par les VRAIES fonctions Python, native_snapshot.py)."""
    import json

    from omega_serv.infrastructure.server.native_snapshot import build_native_snapshot
    return json.dumps(build_native_snapshot(config, project_root, generation, security_processes=security_processes,
                                            notes=notes), ensure_ascii=False).encode("utf-8")


class SnapshotFile:
    """Instantane place dans un memfd scelle (lecture seule), avec sa taille et son empreinte : forme sous laquelle le
    natif le recoit (trame CONFIG + descripteur)."""

    __slots__ = ("digest", "fd", "size")

    def __init__(self, fd: int, size: int, digest: bytes) -> None:
        self.fd = fd
        self.size = size
        self.digest = digest

    def close(self) -> None:
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1


class NativeHealth:
    """Derniere trame HEALTH du natif (classe simple, sans dataclasses : superviseur reduit, lot 5)."""

    __slots__ = ("bytes_in", "bytes_out", "connections", "generation", "proxy_inspections", "proxy_pending_body",
                 "proxy_relayed", "received_at", "rejected", "requests", "upstream_connections", "upstream_idle",
                 "upstream_retries")

    def __init__(self, connections: int = 0, requests: int = 0, rejected: int = 0, generation: int = 0,
                 received_at: float = 0.0, proxy_relayed: int = 0, proxy_pending_body: int = 0,
                 proxy_inspections: int = 0, upstream_connections: int = 0, upstream_retries: int = 0,
                 upstream_idle: int = 0, bytes_in: int | None = None, bytes_out: int | None = None) -> None:
        self.connections = connections
        self.requests = requests
        self.rejected = rejected
        self.generation = generation
        self.received_at = received_at
        # Plan proxy natif v2, lot 4 : relais natif - requetes relayees (cumul) et budgets en cours d'usage (C2)
        self.proxy_relayed = proxy_relayed
        self.proxy_pending_body = proxy_pending_body
        self.proxy_inspections = proxy_inspections
        self.upstream_connections = upstream_connections
        # Lot 5 : nouveaux essais (cumul) et connexions inactives du pool (comptees aussi dans upstream_connections)
        self.upstream_retries = upstream_retries
        self.upstream_idle = upstream_idle
        # Lot 9b (tableau de bord web) : trafic des sites ; None : natif plus ancien, qui ne les envoie pas
        self.bytes_in = bytes_in
        self.bytes_out = bytes_out


class NativeEngine:
    def __init__(self, binary: Path, project_root: Path, threads: int = 0, security_processes: int = 1,
                 spawn: Callable[..., NativeEngineProcess] | None = None,
                 notes_sink: Callable[[str], None] | None = None) -> None:
        self.binary = binary
        self.project_root = project_root
        self.threads = threads
        self.security_processes = security_processes
        """Plan proxy natif v2, lot 3 (P6) : processus de securite ; le fil i est servi par le processus i % N, et
        `/.omega-serv-admin/` va toujours au n° 0 (instantane, inspect.security_processes)."""
        self.spawn: Callable[..., NativeEngineProcess] = spawn or NativeEngineProcess.spawn
        self.notes_sink = notes_sink
        """Plan proxy natif v2, lot 6 : recoit les lignes d'error.log de la construction de l'instantane (adresses des
        noms DNS des backends, backends hors service)."""
        self.process: NativeEngineProcess | None = None
        self.generation = 0
        self.binary_version = ""
        self.health = NativeHealth()
        self.last_error = ""
        """Dernier message ERROR recu du natif (trame refusee de son cote)."""
        self.channel_closed = False
        self._channel: socket.socket | None = None
        self.keep_snapshot = False
        """Lot 5 : garder le memfd scelle de la generation active (`active_snapshot`), pour le superviseur reduit qui le
        renvoie tel quel si le natif doit etre relance - jamais une copie de l'instantane dans le tas."""
        self.active_snapshot: SnapshotFile | None = None

    # ------------------------------------------------------------------ demarrage
    def start(self, config: OmegaServConfig, listen_fds: Sequence[int], data_fds: Sequence[int] = ()) -> None:
        self._start(required_capabilities(config),
                    lambda generation: self.apply_snapshot(self._snapshot(config, generation), None, generation),
                    self.generation + 1, listen_fds, data_fds)

    def start_with_file(self, required: set[str], snapshot: SnapshotFile, generation: int,
                        listen_fds: Sequence[int], data_fds: Sequence[int] = ()) -> None:
        """Lot 5 (superviseur reduit) : relance avec l'instantane deja construit de la generation active."""
        self._start(required, lambda _generation: self.apply_snapshot_file(snapshot, generation), generation,
                    listen_fds, data_fds)

    def _start(self, required: set[str], configure: Callable[[int], str | None], generation: int,
               listen_fds: Sequence[int], data_fds: Sequence[int]) -> None:
        self._close_channel()  # relance apres plantage : l'ancien canal n'a plus de pair
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            self.process = self.spawn(self.binary, listen_fds, child.fileno(), self.threads, data_fds)
        except OSError as e:
            parent.close()
            child.close()
            raise NativeStartError(EXITED, f"lancement impossible : {e}") from e
        child.close()
        self._channel = parent
        self.channel_closed = False
        try:
            self._handshake(required)
            error = configure(generation)
            if error is not None:
                raise NativeStartError(CONFIG_REFUSED, error)
        except NativeStartError:
            self._abort()
            raise
        except (OSError, ipc.FrameError) as e:
            self._abort()
            raise NativeStartError(CHANNEL_ERROR, str(e)) from e

    def adopt(self, pid: int, control_fd: int, binary_version: str, generation: int) -> None:
        """Lot 5 : natif deja lance et configure par le superviseur complet, repris apres sa re-execution."""
        self.process = NativeEngineProcess(pid)
        self._channel = socket.socket(fileno=control_fd)
        self.channel_closed = False
        self.binary_version = binary_version
        self.generation = generation

    def _handshake(self, required: set[str]) -> None:
        hello = self._expect(ipc.HELLO, HELLO_TIMEOUT_SECONDS, NO_HELLO)
        contract = hello.uint(ipc.HELLO_CONTRACT)
        if contract != ipc.CONTRACT_VERSION:
            self._send(ipc.hello_ack(False, f"contrat {contract} different de {ipc.CONTRACT_VERSION}"))
            raise NativeStartError(CONTRACT_MISMATCH, f"binaire au contrat {contract}, attendu {ipc.CONTRACT_VERSION}")
        announced = {value.decode("utf-8", errors="replace") for value in hello.all(ipc.HELLO_CAPABILITY)}
        missing = sorted(required - announced)
        if missing:
            self._send(ipc.hello_ack(False, "capacites manquantes : " + ", ".join(missing)))
            raise NativeStartError(CAPABILITIES_MISSING, ", ".join(missing))
        self.binary_version = hello.text(ipc.HELLO_BINARY) or ""
        self._send(ipc.hello_ack(True))

    # ------------------------------------------------------------------ generations
    def reload(self, config: OmegaServConfig) -> str | None:
        """Nouvelle generation. None si acceptee ; sinon la raison (l'ancienne generation reste active)."""
        generation = self.generation + 1
        return self.reload_with(lambda: self.apply_snapshot(self._snapshot(config, generation), None, generation))

    def reload_with(self, configure: Callable[[], str | None]) -> str | None:
        """`configure` envoie la nouvelle generation (apply_snapshot ou apply_snapshot_file)."""
        try:
            return configure()
        except NativeStartError as e:
            return e.detail
        except (OSError, ipc.FrameError) as e:
            return str(e)

    def _snapshot(self, config: OmegaServConfig, generation: int) -> bytes:
        notes: list[str] = []
        snapshot = snapshot_bytes(config, self.project_root, generation, self.security_processes, notes)
        if self.notes_sink is not None:  # lot 6 : resolution DNS des backends, ecrite dans error.log
            for note in notes:
                self.notes_sink(note)
        return snapshot

    def apply_snapshot(self, snapshot: bytes, digest: bytes | None, generation: int) -> str | None:
        """Envoie une generation et attend son acquittement : None si acceptee, sinon la raison du refus."""
        file = SnapshotFile(ipc.sealed_memfd(snapshot), len(snapshot),
                            digest if digest is not None else ipc.snapshot_digest(snapshot))
        error: str | None = "non envoyee"
        try:
            error = self.apply_snapshot_file(file, generation)
        finally:
            if error is None and self.keep_snapshot:
                self.keep_snapshot_file(file)
            else:
                file.close()
        return error

    def apply_snapshot_file(self, snapshot: SnapshotFile, generation: int) -> str | None:
        """Comme apply_snapshot, l'instantane etant deja dans un memfd scelle ; le memfd reste a l'appelant."""
        self._send(ipc.config_frame_sized(generation, snapshot.size, snapshot.digest), pass_fd=snapshot.fd)
        ack = self._expect(ipc.CONFIG_ACK, CONFIG_ACK_TIMEOUT_SECONDS, CHANNEL_ERROR)
        if ack.generation != generation:
            return f"acquittement de la generation {ack.generation}, attendu {generation}"
        if ack.uint(ipc.CONFIG_OK) != 1:
            errors = [value.decode("utf-8", errors="replace") for value in ack.all(ipc.CONFIG_ERROR)]
            return "; ".join(errors) or "refusee sans raison"
        self.generation = generation
        return None

    def keep_snapshot_file(self, snapshot: SnapshotFile) -> None:
        """Prend le memfd de la generation qui vient d'etre acceptee ; ferme le precedent."""
        if self.active_snapshot is not None and self.active_snapshot is not snapshot:
            self.active_snapshot.close()
        self.active_snapshot = snapshot

    # ------------------------------------------------------------------ canal
    def _send(self, frame: ipc.Frame, pass_fd: int | None = None) -> None:
        assert self._channel is not None
        ipc.send_frame(self._channel, frame, pass_fd)

    def _receive(self, timeout: float | None) -> ipc.Frame | None:
        """Une trame (HEALTH et ERROR consommes au passage) ; None si fin du canal ou rien dans le delai."""
        assert self._channel is not None
        try:
            received = ipc.recv_frame(self._channel, timeout)
        except TimeoutError:
            return None
        if received is None:
            self.channel_closed = True
            return None
        frame, fd = received
        if fd is not None:
            os.close(fd)  # le natif n'envoie jamais de descripteur sur ce canal
        if frame.type == ipc.HEALTH:
            self.health = NativeHealth(
                connections=frame.uint(ipc.HEALTH_CONNECTIONS) or 0,
                requests=frame.uint(ipc.HEALTH_REQUESTS) or 0,
                rejected=frame.uint(ipc.HEALTH_REJECTED) or 0,
                generation=frame.uint(ipc.HEALTH_GENERATION) or 0,
                proxy_relayed=frame.uint(ipc.HEALTH_PROXY_RELAYED) or 0,
                proxy_pending_body=frame.uint(ipc.HEALTH_PROXY_PENDING_BODY) or 0,
                proxy_inspections=frame.uint(ipc.HEALTH_PROXY_INSPECTIONS) or 0,
                upstream_connections=frame.uint(ipc.HEALTH_UPSTREAM_CONNECTIONS) or 0,
                upstream_retries=frame.uint(ipc.HEALTH_UPSTREAM_RETRIES) or 0,
                upstream_idle=frame.uint(ipc.HEALTH_UPSTREAM_IDLE) or 0,
                bytes_in=frame.uint(ipc.HEALTH_BYTES_IN),
                bytes_out=frame.uint(ipc.HEALTH_BYTES_OUT),
                received_at=time.time(),
            )
        elif frame.type == ipc.ERROR:
            self.last_error = frame.text(ipc.ERROR_MESSAGE) or ""
        return frame

    def _expect(self, kind: int, timeout: float, code: str) -> ipc.Frame:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NativeStartError(code, f"pas de reponse du moteur natif en {timeout:.0f} s")
            frame = self._receive(remaining)
            if frame is None and self.channel_closed:
                status = self.process.wait(1.0) if self.process else None
                raise NativeStartError(EXITED, f"le moteur natif s'est arrete (code {status})")
            if frame is not None and frame.type == kind:
                return frame

    def pump(self, timeout: float) -> None:
        """Lit les trames en attente (sante, erreurs) pendant au plus `timeout` secondes."""
        if self._channel is None or self.channel_closed:
            time.sleep(timeout)
            return
        deadline = time.monotonic() + timeout
        while not self.channel_closed:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            ready, _, _ = select.select([self._channel], [], [], remaining)
            if not ready:
                return
            try:
                self._receive(0)
            except (OSError, ipc.FrameError) as e:
                self.last_error = str(e)

    def attach_data_channel(self, thread_index: int, fd: int) -> bool:
        """DATA_ATTACH (lot 4) : nouveau canal de securite pour un fil (processus de securite relance)."""
        if self._channel is None or self.channel_closed:
            return False
        try:
            self._send(ipc.data_attach_frame(thread_index), pass_fd=fd)
        except OSError:
            return False
        return True

    # ------------------------------------------------------------------ vie du processus
    def control_fd(self) -> int:
        return self._channel.fileno() if self._channel is not None else -1

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self, grace_seconds: float) -> int | None:
        """SHUTDOWN (drainage borne par le natif), puis SIGKILL si le delai est largement depasse."""
        if self.process is None:
            return None
        if self._channel is not None and not self.channel_closed:
            try:
                self._send(ipc.shutdown_frame(grace_seconds))
            except OSError:
                pass
        status = self.process.wait(grace_seconds + 5.0)
        if status is None:
            self.process.kill()
            status = self.process.returncode
        self._close_channel()
        return status

    def _abort(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
        self._close_channel()

    def _close_channel(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
