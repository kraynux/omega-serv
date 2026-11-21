"""Fichier de l'historique (lot 7) : var/run/admin/history.json, ecrit par le processus d'administration (au plus
toutes les 5 min et a l'arret), relu a son demarrage. Etat sous var/ seulement."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from omega_serv.infrastructure.admin_web.master_store import _JsonFile
from omega_serv.ports.filesystem_port import FilesystemPort

HISTORY_RELATIVE_PATH = Path("var") / "run" / "admin" / "history.json"


class HistoryStore:
    def __init__(self, filesystem: FilesystemPort, project_root: Path) -> None:
        self._file = _JsonFile(filesystem, project_root / HISTORY_RELATIVE_PATH)

    def load(self) -> dict[str, Any] | None:
        return self._file.read()

    def save(self, data: dict[str, Any]) -> None:
        self._file.write(data, compact=True)  # ~60 Ko plein, au lieu de ~100 Ko indente

    @property
    def path(self) -> Path:
        return self._file.path

