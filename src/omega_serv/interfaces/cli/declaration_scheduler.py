"""Envoi quotidien de la declaration anonyme, pilote depuis `serve` (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b).

Module leger (ni argparse, ni dataclasses) : le superviseur reduit du moteur natif s'en sert aussi (lot 5 memoire,
2026-11-19). `declaration_commands` le reexporte."""
from __future__ import annotations

import os
import signal
import sys
import time
from collections.abc import Callable, Mapping, Sequence

from omega_serv.infrastructure.process.child_process import SpawnedChild

TYPE_CHECKING = False
if TYPE_CHECKING:
    from datetime import datetime

    from omega_serv.ports.declaration_port import DeclarationStorePort

FIRST_CHECK_SECONDS = 60.0
"""Premier controle une minute apres le demarrage : un demarrage n'attend jamais la reception."""
CHECK_EVERY_SECONDS = 3600.0
SPAWN_INTERVAL_SECONDS = 24 * 3600.0
"""Garde-fou en memoire : meme si le journal des envois ne peut pas etre ecrit, jamais plus d'un
envoi par 24 h depuis ce processus."""


class DeclarationScheduler:
    """Pilote l'envoi quotidien depuis `serve`. `tick()` est appele toutes les secondes par la
    boucle du serveur ; il ne fait presque toujours qu'une comparaison d'horloge."""

    def __init__(
        self,
        argv: Sequence[str],
        store: DeclarationStorePort | None,
        *,
        now: Callable[[], datetime],
        environ: Mapping[str, str] = os.environ,
        spawn: Callable[[Sequence[str]], SpawnedChild] = SpawnedChild.spawn,
        monotonic: Callable[[], float] = time.monotonic,
        log: Callable[[str], None] | None = None,
        due: Callable[[], bool] | None = None,
    ) -> None:
        """`due` remplace le controle par defaut (`store`) : le superviseur reduit du natif le fait dans un fils
        ephemere, pour ne jamais garder le code de la declaration en memoire (lot 5, 2026-11-19)."""
        self._argv = list(argv)
        self._store = store
        self._now = now
        self._environ = environ
        self._spawn = spawn
        self._monotonic = monotonic
        self._log = log or (lambda message: print(message, file=sys.stderr))
        self._due_check = due
        self._child: SpawnedChild | None = None
        self._next_check = 0.0
        self._last_spawn: float | None = None

    def start(self) -> None:
        self._next_check = self._monotonic() + FIRST_CHECK_SECONDS

    def tick(self) -> None:
        if self._child is not None and not self._child.is_running():
            self._child = None
        now = self._monotonic()
        if now < self._next_check:
            return
        self._next_check = now + CHECK_EVERY_SECONDS
        if self._child is not None:
            return
        if self._last_spawn is not None and now - self._last_spawn < SPAWN_INTERVAL_SECONDS:
            return
        if not self._due():
            return
        try:
            self._child = self._spawn(self._argv)
        except OSError as error:
            self._log(f"declaration anonyme : lancement de l'envoi impossible ({error})")
        self._last_spawn = now

    def _due(self) -> bool:
        if self._due_check is not None:
            return self._due_check()
        return self.store_says_due()

    def store_says_due(self) -> bool:
        from omega_serv.domain.declaration.model import daily_send_due, do_not_track
        try:
            assert self._store is not None
            stored = self._store.load()
            log = self._store.load_service_log()
        except (OSError, ValueError):
            return False
        attempts = [t for t in (log.last_attempt, stored.last_attempt if stored else None) if t is not None]
        return daily_send_due(stored.declaration if stored else None, max(attempts) if attempts else None,
                              self._now(), do_not_track_set=do_not_track(self._environ))

    def reload(self) -> None:
        """Rien a relire : l'accord et le mode sont relus a chaque controle."""

    def stop(self) -> None:
        """Jamais attendu : un envoi en cours est simplement abandonne."""
        if self._child is not None:
            self._child.send_signal(signal.SIGTERM)
            self._child = None

    def handoff(self) -> dict[str, object]:
        """Voir ChildSupervisor.handoff (superviseur reduit du natif, lot 5)."""
        return {"kind": "declaration", "argv": list(self._argv)}
