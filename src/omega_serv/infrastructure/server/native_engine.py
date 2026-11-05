"""Pilote du moteur natif omega-http-core cote superviseur (plan moteur C++ lot 3 ; contrat IPC §1-6).

Le superviseur ouvre la socket d'ecoute UNE fois et la confie a un seul moteur (§16.5) : ce module lance le
natif avec elle, verifie la poignee de main (version de contrat, capacites), envoie la configuration par
generation (instantane construit par les VRAIES fonctions Python, native_snapshot.py) et attend son
acquittement. Tout echec AVANT le premier acquittement leve `NativeStartError` : le natif est arrete et la
socket reste au superviseur, qui la donne au moteur Python (repli au demarrage, plan §6) - jamais deux moteurs
sur le port, jamais un natif partiellement configure."""
from __future__ import annotations

import json
import os
import select
import socket
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.process.native_engine_process import NativeEngineProcess
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.native_snapshot import build_native_snapshot

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
    needed = {"static", "range", "precompressed", "access_log"}
    if config.security.security_headers_enabled:
        needed.add("security_headers")
    if config.tls.enabled and config.tls.mode == "direct":
        needed.add("tls")
    for option, capability in (("redirects", "redirects"), ("rewrites", "rewrites"), ("aliases", "aliases"),
                               ("access_control", "access_rules"), ("trusted_proxy", "trusted_proxy")):
        if config.option_enabled(option):
            needed.add(capability)
    return needed


@dataclass
class NativeHealth:
    connections: int = 0
    requests: int = 0
    rejected: int = 0
    generation: int = 0
    received_at: float = 0.0


@dataclass
class NativeEngine:
    binary: Path
    project_root: Path
    threads: int = 0
    spawn: Callable[..., NativeEngineProcess] = NativeEngineProcess.spawn
    process: NativeEngineProcess | None = None
    generation: int = 0
    binary_version: str = ""
    health: NativeHealth = field(default_factory=NativeHealth)
    last_error: str = ""
    """Dernier message ERROR recu du natif (trame refusee de son cote)."""
    channel_closed: bool = False
    _channel: socket.socket | None = None

    # ------------------------------------------------------------------ demarrage
    def start(self, config: OmegaServConfig, listen_fds: Sequence[int], data_fds: Sequence[int] = ()) -> None:
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
            self._handshake(config)
            generation = self.generation + 1
            error = self._apply_config(config, generation)
            if error is not None:
                raise NativeStartError(CONFIG_REFUSED, error)
        except NativeStartError:
            self._abort()
            raise
        except (OSError, ipc.FrameError) as e:
            self._abort()
            raise NativeStartError(CHANNEL_ERROR, str(e)) from e

    def _handshake(self, config: OmegaServConfig) -> None:
        hello = self._expect(ipc.HELLO, HELLO_TIMEOUT_SECONDS, NO_HELLO)
        contract = hello.uint(ipc.HELLO_CONTRACT)
        if contract != ipc.CONTRACT_VERSION:
            self._send(ipc.hello_ack(False, f"contrat {contract} different de {ipc.CONTRACT_VERSION}"))
            raise NativeStartError(CONTRACT_MISMATCH, f"binaire au contrat {contract}, attendu {ipc.CONTRACT_VERSION}")
        announced = {value.decode("utf-8", errors="replace") for value in hello.all(ipc.HELLO_CAPABILITY)}
        missing = sorted(required_capabilities(config) - announced)
        if missing:
            self._send(ipc.hello_ack(False, "capacites manquantes : " + ", ".join(missing)))
            raise NativeStartError(CAPABILITIES_MISSING, ", ".join(missing))
        self.binary_version = hello.text(ipc.HELLO_BINARY) or ""
        self._send(ipc.hello_ack(True))

    # ------------------------------------------------------------------ generations
    def reload(self, config: OmegaServConfig) -> str | None:
        """Nouvelle generation. None si acceptee ; sinon la raison (l'ancienne generation reste active)."""
        try:
            return self._apply_config(config, self.generation + 1)
        except NativeStartError as e:
            return e.detail
        except (OSError, ipc.FrameError) as e:
            return str(e)

    def _apply_config(self, config: OmegaServConfig, generation: int) -> str | None:
        snapshot = json.dumps(build_native_snapshot(config, self.project_root, generation), ensure_ascii=False).encode("utf-8")
        memfd = ipc.sealed_memfd(snapshot)
        try:
            self._send(ipc.config_frame(generation, snapshot), pass_fd=memfd)
        finally:
            os.close(memfd)
        ack = self._expect(ipc.CONFIG_ACK, CONFIG_ACK_TIMEOUT_SECONDS, CHANNEL_ERROR)
        if ack.generation != generation:
            return f"acquittement de la generation {ack.generation}, attendu {generation}"
        if ack.uint(ipc.CONFIG_OK) != 1:
            errors = [value.decode("utf-8", errors="replace") for value in ack.all(ipc.CONFIG_ERROR)]
            return "; ".join(errors) or "refusee sans raison"
        self.generation = generation
        return None

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
