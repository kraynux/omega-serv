"""Processus du moteur natif omega-http-core (plan moteur C++ lot 3, §2 : « lance le binaire natif par exec »).

`os.posix_spawn` comme RIPOSTE (child_process.py) : jamais de `fork` d'un superviseur qui a peut-etre des fils.
Seuls la socket d'ecoute et l'extremite « natif » du canal de controle sont transmis : ils deviennent
heritables le temps du lancement, puis redeviennent non heritables - aucun autre processus lance plus tard
(RIPOSTE, relance du natif) ne les recoit par accident. Tout autre descripteur du superviseur est deja
non heritable (PEP 446)."""
from __future__ import annotations

import os
import signal
import time
from collections.abc import Sequence
from pathlib import Path

from omega_serv.application.server.engine_selection import BINARY_MISSING, BINARY_NOT_EXECUTABLE


def native_binary_problem(binary: Path) -> str | None:
    """None si le binaire est utilisable, sinon le code de raison (engine_selection)."""
    if not binary.is_file():
        return BINARY_MISSING
    if not os.access(binary, os.X_OK):
        return BINARY_NOT_EXECUTABLE
    return None


class NativeEngineProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.returncode: int | None = None
        """Code de sortie (negatif = tue par ce signal), None tant qu'il tourne."""

    @classmethod
    def spawn(cls, binary: Path, listen_fds: Sequence[int], control_fd: int, threads: int = 0,
              data_fds: Sequence[int] = ()) -> NativeEngineProcess:
        argv = [str(binary), "--control-fd", str(control_fd)]
        for fd in listen_fds:
            argv += ["--listen-fd", str(fd)]
        if threads > 0:
            argv += ["--threads", str(threads)]
        for fd in data_fds:  # lot 4 : un canal INSPECT/VERDICT par fil, dans l'ordre des fils
            argv += ["--data-fd", str(fd)]
        passed = [*listen_fds, control_fd, *data_fds]
        for fd in passed:
            os.set_inheritable(fd, True)
        try:
            pid = os.posix_spawn(str(binary), argv, dict(os.environ))
        finally:
            for fd in passed:
                os.set_inheritable(fd, False)
        return cls(pid)

    def poll(self) -> int | None:
        if self.returncode is not None:
            return self.returncode
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self.returncode = 0  # deja recolte ailleurs : termine, code inconnu
            return self.returncode
        if pid == self.pid:
            self.returncode = os.waitstatus_to_exitcode(status)
        return self.returncode

    def wait(self, timeout: float) -> int | None:
        deadline = time.monotonic() + timeout
        while self.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        return self.returncode

    def send_signal(self, sig: signal.Signals) -> None:
        if self.poll() is None:
            try:
                os.kill(self.pid, sig)
            except ProcessLookupError:
                pass

    def kill(self) -> None:
        self.send_signal(signal.SIGKILL)
        self.wait(5.0)
