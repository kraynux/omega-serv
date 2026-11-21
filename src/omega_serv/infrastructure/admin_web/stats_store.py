"""var/lib/admin/stats/AAAA-MM-JJ.json (etude modules, module 2) : compteurs d'un jour, 660, 31 jours gardes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from omega_serv.ports.filesystem_port import FilesystemPort

STATS_RELATIVE_DIR = Path("var") / "lib" / "admin" / "stats"
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class StatsStore:
    def __init__(self, filesystem: FilesystemPort, project_root: Path) -> None:
        self._filesystem = filesystem
        self._directory = project_root / STATS_RELATIVE_DIR

    def _path(self, day: str) -> Path:
        if not _DAY.match(day):
            raise ValueError(day)
        return self._directory / f"{day}.json"

    def load(self, day: str) -> dict[str, Any] | None:
        path = self._path(day)
        try:
            data = json.loads(self._filesystem.read_text(path)) if self._filesystem.is_file(path) else None
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def save(self, day: str, data: dict[str, Any]) -> None:
        if not self._filesystem.is_dir(self._directory):
            self._filesystem.make_directory(self._directory, 0o2770)
        self._filesystem.atomic_write_text(self._path(day), json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                                           min_mode=0o660)

    def days(self) -> list[str]:
        if not self._filesystem.is_dir(self._directory):
            return []
        try:
            names = self._filesystem.list_directory_entries(self._directory)
        except OSError:
            return []
        return sorted(name[:-5] for name in names if name.endswith(".json") and _DAY.match(name[:-5]))

    def remove(self, day: str) -> None:
        try:
            self._filesystem.delete_file(self._path(day))
        except OSError:
            pass
