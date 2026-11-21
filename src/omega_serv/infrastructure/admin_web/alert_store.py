"""Fichiers des alertes locales (etude modules, module 1) : var/lib/admin/alertes.json (ouvertes et historique),
var/lib/admin/alertes-maintenance.json (ecrit par la TUI), var/log/alertes.log (une ligne par evenement). Fichiers
660 : ecrits par le processus d'administration (compte du service), lus et ecrits par la TUI (groupe)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from omega_serv.ports.filesystem_port import FilesystemPort

ALERTS_RELATIVE_PATH = Path("var") / "lib" / "admin" / "alertes.json"
MAINTENANCE_RELATIVE_PATH = Path("var") / "lib" / "admin" / "alertes-maintenance.json"
LOG_RELATIVE_PATH = Path("var") / "log" / "alertes.log"


class AlertStore:
    def __init__(self, filesystem: FilesystemPort, project_root: Path) -> None:
        self._filesystem = filesystem
        self._root = project_root

    def _read(self, relative: Path) -> Any:
        path = self._root / relative
        try:
            return json.loads(self._filesystem.read_text(path)) if self._filesystem.is_file(path) else None
        except (OSError, ValueError):
            return None

    def load(self) -> dict[str, Any] | None:
        data = self._read(ALERTS_RELATIVE_PATH)
        return data if isinstance(data, dict) else None

    def save(self, data: dict[str, Any]) -> None:
        path = self._root / ALERTS_RELATIVE_PATH
        if not self._filesystem.is_dir(path.parent):
            self._filesystem.make_directory(path.parent, 0o2770)
        self._filesystem.atomic_write_text(path, json.dumps(data, ensure_ascii=False), min_mode=0o660)

    def log(self, line: str) -> None:
        path = self._root / LOG_RELATIVE_PATH
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o660)
            try:
                os.write(fd, f"{stamp} {line}\n".encode())
            finally:
                os.close(fd)
        except OSError:
            pass

    def maintenance_until(self) -> float | None:
        data = self._read(MAINTENANCE_RELATIVE_PATH)
        until = data.get("jusqu_a") if isinstance(data, dict) else None
        return float(until) if isinstance(until, int | float) and not isinstance(until, bool) else None

    def set_maintenance(self, until: float | None) -> None:
        path = self._root / MAINTENANCE_RELATIVE_PATH
        if until is None:
            if self._filesystem.exists(path):
                self._filesystem.delete_file(path)
            return
        if not self._filesystem.is_dir(path.parent):
            self._filesystem.make_directory(path.parent, 0o2770)
        self._filesystem.atomic_write_text(path, json.dumps({"jusqu_a": until}), min_mode=0o660)
