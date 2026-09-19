"""Persistance JSON des `SnapshotMetadata` (plan interface §3.5) - un
fichier `<snapshot_id>.json` a cote de chaque `<snapshot_id>.tar.gz`
ecrit par `ArchiveStore` dans le meme repertoire (les motifs de recherche
`*.tar.gz`/`*.json` ne se chevauchent jamais, aucun sous-repertoire
separe necessaire). `ArchiveStore` ne modelise que des archives
generiques (nom/taille/date de modification) - cette classe est le seul
endroit qui connait la forme `SnapshotMetadata` reelle (scope,
description, statut...), meme separation domaine/infrastructure que le
reste du projet."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from omega_serv.domain.persistence.snapshots import SnapshotMetadata, SnapshotStatus


def _to_dict(metadata: SnapshotMetadata) -> dict:
    return {
        "snapshot_id": metadata.snapshot_id,
        "created_at": metadata.created_at.isoformat(),
        "scope": metadata.scope,
        "description": metadata.description,
        "version": metadata.version,
        "source_system": metadata.source_system,
        "hostname": metadata.hostname,
        "os_info": metadata.os_info,
        "app_version": metadata.app_version,
        "status": metadata.status.value,
        "error_message": metadata.error_message,
        "file_path": metadata.file_path,
        "file_size_bytes": metadata.file_size_bytes,
    }


def _from_dict(data: dict) -> SnapshotMetadata:
    return SnapshotMetadata(
        snapshot_id=data["snapshot_id"],
        created_at=datetime.fromisoformat(data["created_at"]),
        scope=data["scope"],
        description=data.get("description", ""),
        version=data.get("version", "1.0"),
        source_system=data.get("source_system", "omega-serv"),
        hostname=data.get("hostname"),
        os_info=data.get("os_info"),
        app_version=data.get("app_version"),
        status=SnapshotStatus(data.get("status", SnapshotStatus.COMPLETED.value)),
        error_message=data.get("error_message"),
        file_path=data.get("file_path"),
        file_size_bytes=data.get("file_size_bytes"),
    )


class BackupMetadataStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, snapshot_id: str) -> Path:
        return self._base_dir / f"{snapshot_id}.json"

    def save(self, metadata: SnapshotMetadata) -> None:
        self._path_for(metadata.snapshot_id).write_text(
            json.dumps(_to_dict(metadata), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load(self, snapshot_id: str) -> SnapshotMetadata | None:
        path = self._path_for(snapshot_id)
        if not path.exists():
            return None
        return _from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_all(self) -> list[SnapshotMetadata]:
        items = [self.load(path.stem) for path in self._base_dir.glob("*.json")]
        return sorted((m for m in items if m is not None), key=lambda m: m.created_at, reverse=True)

    def delete(self, snapshot_id: str) -> bool:
        path = self._path_for(snapshot_id)
        if path.exists():
            path.unlink()
            return True
        return False
