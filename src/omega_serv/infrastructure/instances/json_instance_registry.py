"""Implementation reelle de InstanceRegistryPort - fichier JSON unique,
`~/.config/omega-serv/instances.json` par convention (voir
bootstrap/paths.py::INSTANCE_REGISTRY_PATH, jamais code en dur ici -
le chemin reste injectable pour les tests, meme regime que
systemd_unit_dir)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.ports.filesystem_port import FilesystemPort


class JsonInstanceRegistry:
    """Implemente ports.instance_registry_port.InstanceRegistryPort."""

    def __init__(self, filesystem: FilesystemPort, path: Path) -> None:
        self._fs = filesystem
        self._path = path

    def load(self) -> list[InstanceEntry]:
        if not self._fs.exists(self._path):
            return []
        raw = json.loads(self._fs.read_text(self._path))
        return [
            InstanceEntry(
                name=item["name"],
                path=Path(item["path"]),
                bind=item["bind"],
                port=item["port"],
                service_name=item["service_name"],
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in raw
        ]

    def save(self, entries: list[InstanceEntry]) -> None:
        self._fs.make_directory(self._path.parent, mode=0o700)
        data = [
            {
                "name": e.name, "path": str(e.path), "bind": e.bind, "port": e.port,
                "service_name": e.service_name, "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]
        self._fs.atomic_write_text(self._path, json.dumps(data, indent=2, ensure_ascii=False))
