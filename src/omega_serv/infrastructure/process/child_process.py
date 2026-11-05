"""Processus enfant de longue duree (RIPOSTE, OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.1, lot 2).

`os.posix_spawn` (fork + exec par le noyau/la libc) : l'enfant demarre un interpreteur neuf, il
n'herite d'aucun etat Python du parent - ni fils, ni verrous, ni boucle asyncio, ni compteurs
partages. C'est ce qui permet de le lancer depuis le superviseur du mode boost (qui lui-meme
`fork` ses workers) sans le piege « fork + fils ».

Suivi par `waitpid(pid, WNOHANG)` sur SON pid uniquement : en mode boost, le superviseur recolte
deja ses workers par `waitpid(-1)` et peut donc recolter celui-ci a sa place - `ChildProcessError`
(ECHILD) veut alors simplement dire « termine », jamais une erreur."""
from __future__ import annotations

import os
import signal
import time
from collections.abc import Mapping, Sequence


class SpawnedChild:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._ended = False

    @classmethod
    def spawn(cls, argv: Sequence[str], env: Mapping[str, str] | None = None) -> SpawnedChild:
        pid = os.posix_spawn(argv[0], list(argv), dict(os.environ if env is None else env))
        return cls(pid)

    def is_running(self) -> bool:
        if self._ended:
            return False
        try:
            pid, _status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            pid = self.pid  # deja recolte par quelqu'un d'autre (superviseur boost) : termine
        if pid == self.pid:
            self._ended = True
        return not self._ended

    def send_signal(self, sig: signal.Signals) -> None:
        if not self._ended:
            try:
                os.kill(self.pid, sig)
            except ProcessLookupError:
                self._ended = True

    def stop(self, grace_seconds: float) -> None:
        """SIGTERM, puis SIGKILL si l'enfant ne s'est pas arrete dans le delai."""
        self.send_signal(signal.SIGTERM)
        deadline = time.monotonic() + grace_seconds
        while self.is_running() and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.is_running():
            self.send_signal(signal.SIGKILL)
            while self.is_running():
                time.sleep(0.05)
