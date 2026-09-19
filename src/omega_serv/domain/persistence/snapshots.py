"""Metadonnees pures d'une sauvegarde de configuration (plan interface
§3.5/§10, port adapte depuis omega-fire domain/persistence/snapshots.py::
SnapshotMetadata - seule piece identifiee comme generique et reutilisable
telle quelle, voir le plan). `SnapshotScope`/`SnapshotOrigin` de fire
(enums fermes FULL/BLACKLIST_ONLY/RULES_ONLY/FAIL2BAN_ONLY/CUSTOM et
MANUAL/AUTO_PRESET) ne sont pas portes : cote SERV le contenu d'une
sauvegarde vient de combinaisons de flags (`BackupRequest`), pas d'une
taxonomie fermee, et rien ne declenche jamais une sauvegarde
automatiquement (pas d'equivalent aux "presets" de fire, menu 3.4) -
`scope` reste une simple chaine descriptive (ex. "config+waf") et
`origin` n'existe pas ici (toujours manuel). `SnapshotStatus` est
trimme a ce qui est reellement atteignable par ce mecanisme
(sauvegarde/restauration synchrones, pas de verification de checksum) :
PENDING (jamais d'etat intermediaire observable, l'ecriture est
synchrone) et CORRUPTED (aucune verification d'integrite construite)
de fire ne sont pas portes, meme discipline D-008 que le trim de
domain/logs/rotation.py en Phase VI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SnapshotStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORED = "restored"


@dataclass(frozen=True)
class SnapshotMetadata:
    snapshot_id: str
    created_at: datetime
    scope: str
    description: str = ""
    version: str = "1.0"
    source_system: str = "omega-serv"
    hostname: str | None = None
    os_info: str | None = None
    app_version: str | None = None
    status: SnapshotStatus = SnapshotStatus.COMPLETED
    error_message: str | None = None
    file_path: str | None = None
    file_size_bytes: int | None = None


def create_snapshot_id(timestamp: datetime) -> str:
    return f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
