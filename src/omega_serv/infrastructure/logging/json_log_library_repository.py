"""Implementation JSON du port LogLibraryRepositoryPort (gestion des
logs, refonte menu 2026-10-15) - meme convention que le reste du
projet (JSON pour la configuration legere, pas SQLite)."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.domain.logs.library import LibraryRecord


class JsonLogLibraryRepository:
    """Deduplique par `path` - un meme chemin ne peut etre reference
    qu'une fois (un ajout repete remplace l'entree existante)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def list_all(self) -> list[LibraryRecord]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [LibraryRecord(**entry) for entry in raw]

    def add(self, record: LibraryRecord) -> None:
        records = {r.path: r for r in self.list_all()}
        records[record.path] = record
        self._write(list(records.values()))

    def remove(self, path: str) -> None:
        records = [r for r in self.list_all() if r.path != path]
        self._write(records)

    def contains(self, path: str) -> bool:
        return any(r.path == path for r in self.list_all())

    def _write(self, records: list[LibraryRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [{"path": r.path, "access": r.access, "service_id": r.service_id} for r in records]
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
