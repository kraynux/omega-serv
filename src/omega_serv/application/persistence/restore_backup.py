"""Cas d'usage : restaurer une sauvegarde de configuration (plan
interface §3.5/§10). Extrait directement sur `project_root` (les
arcnames de l'archive sont relatifs a la racine du projet, voir
create_backup.py) - ecrase les fichiers existants aux memes chemins,
aucune sauvegarde automatique prealable n'est prise (la restauration
EST l'operation de recuperation ; creer une sauvegarde avant de
restaurer reste a l'initiative de l'utilisateur, cf. §14 du plan)."""
from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.domain.persistence.snapshots import SnapshotStatus
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore

DATABASE_SUFFIX = ".sqlite3"
SQLITE_SIDE_FILES = ("-wal", "-shm")


@dataclasses.dataclass(frozen=True)
class RestoreResult:
    success: bool
    message: str
    needs_service_stop: bool = False
    """La sauvegarde contient une base et le serveur tourne : refusee (decision utilisateur 2026-11-01) -
    l'interface propose « Arreter, restaurer, redemarrer »."""
    databases: tuple[str, ...] = ()


def archive_databases(archive_store: ArchiveStore, archive_path: Path) -> tuple[str, ...]:
    """Bases SQLite contenues dans l'archive (Active Defense, RIPOSTE), chemins relatifs au projet."""
    return tuple(name for name in archive_store.list_members(archive_path) if name.endswith(DATABASE_SUFFIX))


def _set_aside_databases(databases: tuple[str, ...], project_root: Path, aside_dir: Path) -> None:
    """Avant d'ecraser une base : la base actuelle ET ses fichiers -wal/-shm sont deplaces de cote
    (retour arriere possible). Un ancien -wal laisse en place serait rejoue sur la base restauree et
    la corromprait."""
    for relative in databases:
        for suffix in ("", *SQLITE_SIDE_FILES):
            current = project_root / (relative + suffix)
            if current.exists():
                target = aside_dir / (relative + suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(current), str(target))


def restore_backup(
    snapshot_id: str,
    project_root: Path,
    archive_store: ArchiveStore,
    metadata_store: BackupMetadataStore,
    *,
    server_running: bool = False,
    aside_dir: Path | None = None,
) -> RestoreResult:
    """`server_running` : une sauvegarde qui contient une base n'est jamais restauree sous un serveur
    actif (les workers et RIPOSTE ecrivent dans ces bases). `aside_dir` : ou mettre de cote les bases
    remplacees (par defaut a cote des sauvegardes)."""
    metadata = metadata_store.load(snapshot_id)
    if metadata is None:
        return RestoreResult(False, _("Sauvegarde introuvable : {snapshot_id}").format(snapshot_id=snapshot_id))
    if metadata.file_path is None:
        return RestoreResult(False, _("Sauvegarde invalide (chemin d'archive manquant) : {snapshot_id}").format(snapshot_id=snapshot_id))

    archive_path = Path(metadata.file_path)
    try:
        databases = archive_databases(archive_store, archive_path)
    except ArchiveStoreError as exc:
        metadata_store.save(dataclasses.replace(metadata, status=SnapshotStatus.FAILED, error_message=str(exc)))
        return RestoreResult(False, _("Échec de restauration : {exc}").format(exc=exc))
    if databases and server_running:
        return RestoreResult(
            False,
            _("Cette sauvegarde contient une base ({databases}) et le serveur tourne : restauration refusée. "
              "Arrêter le serveur, restaurer, puis redémarrer.").format(databases=", ".join(databases)),
            needs_service_stop=True, databases=databases,
        )
    try:
        if databases:
            _set_aside_databases(
                databases, project_root,
                aside_dir or archive_store.base_dir / f"avant-restauration-{snapshot_id}",
            )
        archive_store.extract_archive(archive_path, project_root)
    except (ArchiveStoreError, OSError) as exc:
        metadata_store.save(dataclasses.replace(metadata, status=SnapshotStatus.FAILED, error_message=str(exc)))
        return RestoreResult(False, _("Échec de restauration : {exc}").format(exc=exc), databases=databases)

    metadata_store.save(dataclasses.replace(metadata, status=SnapshotStatus.RESTORED, error_message=None))
    return RestoreResult(True, _("Sauvegarde restaurée : {snapshot_id}.").format(snapshot_id=snapshot_id), databases=databases)
