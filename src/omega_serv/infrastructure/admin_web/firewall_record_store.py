# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ouverture du port de l'administration web par omega-fire (sous-lot 8b) : var/lib/admin/pare-feu.json, ecrit par
la TUI apres une ouverture reussie, lu pour le bilan de Configuration distante. Etat sous var/ seulement."""
from __future__ import annotations

import contextlib
from pathlib import Path

from omega_serv.application.admin_web.firewall_setup import FirewallRecord
from omega_serv.infrastructure.admin_web.master_store import _JsonFile
from omega_serv.ports.filesystem_port import FilesystemPort

FIREWALL_RECORD_RELATIVE_PATH = Path("var") / "lib" / "admin" / "pare-feu.json"


class FirewallRecordStore:
    def __init__(self, filesystem: FilesystemPort, project_root: Path) -> None:
        self._file = _JsonFile(filesystem, project_root / FIREWALL_RECORD_RELATIVE_PATH)

    def save(self, record: FirewallRecord) -> bool:
        try:
            self._file.write(record.to_dict())
        except OSError:
            return False
        return True

    def load(self) -> FirewallRecord | None:
        with contextlib.suppress(OSError, ValueError):
            return FirewallRecord.from_dict(self._file.read())
        return None
