"""var/run/admin/sessions.json (liste publiee toutes les 5 s par le processus d'administration, sans jeton : compte,
adresse, mode, dates, identifiant public) et var/run/admin/sessions-a-fermer.json (demandes de la TUI). Fichiers 660
dans var/run/admin (partage avec le groupe du service). Etude modules, module 5."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from omega_serv.ports.filesystem_port import FilesystemPort

SESSIONS_RELATIVE_PATH = Path("var") / "run" / "admin" / "sessions.json"
REQUESTS_RELATIVE_PATH = Path("var") / "run" / "admin" / "sessions-a-fermer.json"
MAX_REQUESTS = 100


class SessionFiles:
    def __init__(self, filesystem: FilesystemPort, project_root: Path, clock: Any = time.time) -> None:
        self._filesystem = filesystem
        self._root = project_root
        self._clock = clock

    def _write(self, relative: Path, data: Any) -> None:
        path = self._root / relative
        if not self._filesystem.is_dir(path.parent):
            self._filesystem.make_directory(path.parent, 0o2770)
        self._filesystem.atomic_write_text(path, json.dumps(data, ensure_ascii=False), min_mode=0o660)

    def _read(self, relative: Path) -> Any:
        path = self._root / relative
        try:
            return json.loads(self._filesystem.read_text(path)) if self._filesystem.is_file(path) else None
        except (OSError, ValueError):
            return None

    def publish(self, sessions: list[dict[str, Any]]) -> None:
        try:
            self._write(SESSIONS_RELATIVE_PATH, {"publie": self._clock(), "sessions": sessions})
        except OSError:
            pass

    def published(self) -> tuple[float, list[dict[str, Any]]] | None:
        data = self._read(SESSIONS_RELATIVE_PATH)
        if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
            return None
        stamp = data.get("publie")
        return (float(stamp) if isinstance(stamp, int | float) else 0.0,
                [item for item in data["sessions"] if isinstance(item, dict)])

    def request_close(self, public_id: str) -> None:
        current = self._read(REQUESTS_RELATIVE_PATH)
        ids = [i for i in current if isinstance(i, str)] if isinstance(current, list) else []
        if public_id not in ids:
            ids.append(public_id)
        self._write(REQUESTS_RELATIVE_PATH, ids[-MAX_REQUESTS:])

    def take_close_requests(self) -> list[str]:
        data = self._read(REQUESTS_RELATIVE_PATH)
        path = self._root / REQUESTS_RELATIVE_PATH
        if data is None:
            return []
        try:
            self._filesystem.delete_file(path)
        except OSError:
            return []  # pas le droit de la retirer : ne jamais fermer deux fois en boucle
        return [i for i in data if isinstance(i, str) and len(i) == 12][:MAX_REQUESTS] if isinstance(data, list) else []
