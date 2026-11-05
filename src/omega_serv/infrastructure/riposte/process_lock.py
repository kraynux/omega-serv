"""Un seul processus RIPOSTE par instance (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.1) : verrou flock
non bloquant sur `var/run/riposte.lock`, tenu toute la vie du processus et relache par le noyau
s'il meurt (jamais un fichier PID perime qui empecherait de redemarrer)."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path

LOCK_FILE_MODE = 0o664


class ProcessLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: int | None = None

    def acquire(self) -> bool:
        """Vrai si ce processus est desormais le proprietaire, faux si un autre l'est deja."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_RDONLY | os.O_CREAT, LOCK_FILE_MODE)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
