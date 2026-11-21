"""Sessions ouvertes publiees pour la TUI et fermetures demandees par elle (etude modules, module 5) : toutes les
5 s dans le processus d'administration ; ecrit seulement quand la liste change."""
from __future__ import annotations

import asyncio
from typing import Any

from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.ports.admin_sessions_port import SessionFilesPort

PUBLISH_SECONDS = 5.0


def session_rows(auth: AdminAuth) -> list[dict[str, Any]]:
    return [{"id": s.public_id, "compte": s.username, "adresse": s.ip, "mode": s.mode, "ouverte": round(s.created),
             "activite": round(s.last_seen)} for s in auth.open_sessions()]


class SessionPublisher:
    def __init__(self, files: SessionFilesPort, auth: Any) -> None:
        self._files = files
        self._auth = auth
        """Callable rendant l'AdminAuth courant (ou None avant le premier demarrage)."""
        self._last: list[dict[str, Any]] | None = None

    def tick(self) -> None:
        auth: AdminAuth | None = self._auth()
        if auth is None:
            return
        for public_id in self._files.take_close_requests():
            auth.close_session(public_id, "TUI", "local")
        rows = session_rows(auth)
        comparable = [{k: v for k, v in row.items() if k != "activite"} for row in rows]
        if comparable != self._last:
            self._last = comparable
            self._files.publish(rows)

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self.tick()
            try:
                await asyncio.wait_for(stop.wait(), PUBLISH_SECONDS)
            except TimeoutError:
                pass
