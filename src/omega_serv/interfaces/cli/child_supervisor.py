"""Supervision d'un processus enfant de longue duree lance par `serve` (RIPOSTE, administration web).

Lance, surveille, relance (avec garde-fou), recharge et arrete le processus. Une panne de l'enfant n'arrete jamais
le serveur web : passe le garde-fou (trop d'arrets rapproches), c'est l'enfant seul qui reste arrete. Messages vers
journalctl en francais (D18b, comme `serve`). Sorti de riposte_commands.py pour le tableau de bord web (lot 2,
2026-11-16), sans changer le comportement ni les messages de RIPOSTE."""
from __future__ import annotations

import signal
import sys
import time
from collections.abc import Callable, Sequence

from omega_serv.infrastructure.process.child_process import SpawnedChild

RESTART_WINDOW_SECONDS = 60.0
MAX_RESTARTS_IN_WINDOW = 5
STOP_GRACE_SECONDS = 5.0


class ChildSupervisor:
    """`tick()` est appele regulierement par le serveur (toutes les secondes) ; jamais bloquant hors de `stop()`."""

    def __init__(
        self,
        label: str,
        argv: Sequence[str],
        *,
        spawn: Callable[[Sequence[str]], SpawnedChild] = SpawnedChild.spawn,
        monotonic: Callable[[], float] = time.monotonic,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self._label = label
        self._argv = list(argv)
        self._spawn = spawn
        self._monotonic = monotonic
        self._log = log or (lambda message: print(message, file=sys.stderr))
        self._child: SpawnedChild | None = None
        self._deaths: list[float] = []
        self.gave_up = False

    def start(self) -> None:
        try:
            self._child = self._spawn(self._argv)
        except OSError as error:
            self._log(f"{self._label} : lancement impossible ({error}) - le serveur web continue sans {self._label}")
            self.gave_up = True
            return
        print(f"{self._label} lance (PID {self._child.pid})")

    def tick(self) -> None:
        if self.gave_up or self._child is None or self._child.is_running():
            return
        now = self._monotonic()
        self._deaths[:] = [t for t in self._deaths if now - t < RESTART_WINDOW_SECONDS] + [now]
        if len(self._deaths) > MAX_RESTARTS_IN_WINDOW:
            self._log(
                f"{self._label} arrete {len(self._deaths)} fois en {int(RESTART_WINDOW_SECONDS)} s : plus de relance "
                f"(le serveur web continue ; voir les messages de {self._label} ci-dessus)"
            )
            self.gave_up = True
            self._child = None
            return
        self._log(f"{self._label} (PID {self._child.pid}) arrete de facon inattendue : relance")
        self.start()

    def reload(self) -> None:
        if self._child is not None:
            self._child.send_signal(signal.SIGHUP)

    def stop(self) -> None:
        if self._child is not None:
            self._child.stop(STOP_GRACE_SECONDS)
            self._child = None

    def handoff(self) -> dict[str, object]:
        """Description transmise au superviseur reduit du natif (lot 5), qui le recree a l'identique avant de le
        lancer : `serve` ne lance jamais ses compagnons avant la re-execution."""
        return {"kind": "child", "label": self._label, "argv": list(self._argv)}


class ServeCompanions:
    """Processus accompagnant `serve` (RIPOSTE, envoi quotidien, administration web), pilotes ensemble : meme
    contrat que RiposteChildPort (start, tick, reload, stop)."""

    def __init__(self, *members: object) -> None:
        self._members = [member for member in members if member is not None]

    def start(self) -> None:
        for member in self._members:
            member.start()  # type: ignore[attr-defined]

    def tick(self) -> None:
        for member in self._members:
            member.tick()  # type: ignore[attr-defined]

    def reload(self) -> None:
        for member in self._members:
            member.reload()  # type: ignore[attr-defined]

    def stop(self) -> None:
        for member in self._members:
            member.stop()  # type: ignore[attr-defined]

    def handoff(self) -> list[dict[str, object]]:
        return [member.handoff() for member in self._members]  # type: ignore[attr-defined]
