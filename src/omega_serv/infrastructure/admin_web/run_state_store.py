# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fichier d'etat du processus d'administration (lot 8) : var/run/admin/etat.json. Ecrit par le processus (compte du
service), lu par la TUI (groupe du service). Un etat dont le processus n'existe plus est ignore."""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

from omega_serv.domain.admin_web.run_state import AdminRunState
from omega_serv.infrastructure.admin_web.master_store import _JsonFile
from omega_serv.ports.filesystem_port import FilesystemPort

RUN_STATE_RELATIVE_PATH = Path("var") / "run" / "admin" / "etat.json"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # processus d'un autre compte (le service) : il existe
    except OSError:
        return False
    return True


class AdminRunStateStore:
    def __init__(self, filesystem: FilesystemPort, project_root: Path) -> None:
        self._file = _JsonFile(filesystem, project_root / RUN_STATE_RELATIVE_PATH)

    def save(self, state: AdminRunState) -> None:
        with contextlib.suppress(OSError):  # dossier non inscriptible : l'administration demarre quand meme
            self._file.write(state.to_dict(), compact=True)

    def load(self) -> AdminRunState | None:
        """None : jamais ecrit, illisible (session sans le groupe du service) ou processus disparu."""
        try:
            state = AdminRunState.from_dict(self._file.read())
        except (OSError, ValueError):
            return None
        if state is None or not _alive(state.pid):
            return None
        return state
