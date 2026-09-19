"""Cas d'usage : restaurer une sauvegarde de configuration (plan
interface §3.5/§10). Extrait directement sur `project_root` (les
arcnames de l'archive sont relatifs a la racine du projet, voir
create_backup.py) - ecrase les fichiers existants aux memes chemins,
aucune sauvegarde automatique prealable n'est prise (la restauration
EST l'operation de recuperation ; creer une sauvegarde avant de
restaurer reste a l'initiative de l'utilisateur, cf. §14 du plan)."""
from __future__ import annotations

import dataclasses
from pathlib import Path

from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.domain.persistence.snapshots import SnapshotStatus
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore


@dataclasses.dataclass(frozen=True)
class RestoreResult:
    success: bool
    message: str


def restore_backup(
    snapshot_id: str,
    project_root: Path,
    archive_store: ArchiveStore,
    metadata_store: BackupMetadataStore,
) -> RestoreResult:
    metadata = metadata_store.load(snapshot_id)
    if metadata is None:
        return RestoreResult(False, f"Sauvegarde introuvable : {snapshot_id}")
    if metadata.file_path is None:
        return RestoreResult(False, f"Sauvegarde invalide (chemin d'archive manquant) : {snapshot_id}")

    archive_path = Path(metadata.file_path)
    try:
        archive_store.extract_archive(archive_path, project_root)
    except ArchiveStoreError as exc:
        metadata_store.save(dataclasses.replace(metadata, status=SnapshotStatus.FAILED, error_message=str(exc)))
        return RestoreResult(False, f"Echec de restauration : {exc}")

    metadata_store.save(dataclasses.replace(metadata, status=SnapshotStatus.RESTORED, error_message=None))
    return RestoreResult(True, f"Sauvegarde restauree : {snapshot_id}.")
