# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Exporter et importer une sauvegarde, lire ce qu'elle annonce (projets 3.0.0 §7.4, decisions de l'auteur du
2026-11-15).

Objectif : desinstaller omega-serv, le reinstaller, et retrouver le serveur dans son etat a partir d'un fichier.
Avant, une sauvegarde restait dans `var/backups/` de l'instance : supprimer le dossier l'effacait aussi, et la
restauration ne voyait que ce dossier.

- **Export** : copie de l'archive vers un dossier choisi, avec son empreinte `.sha256` (format sha256sum).
- **Import** : refuse tout ce qui n'est pas une sauvegarde omega-serv saine - empreinte absente ou fausse, chemin
  absolu, `..`, lien, peripherique, dossier de premier niveau inconnu (seuls s'ajoutent au webroot les dossiers de
  zones que la configuration de l'archive designe), taille demesuree, archive sans
  `config/omega-serve.json`. L'archive acceptee rejoint la liste ; la restauration reste une etape separee,
  confirmee, avec le resume de ce qui sera remplace.
- **Identite** : adresse, port, nom du service et version annonces par l'archive, pour signaler un conflit de port
  avec une autre instance ou une version differente AVANT de restaurer."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from omega_serv.application.persistence.backup_manifest import MANIFEST_NAME
from omega_serv.application.persistence.zone_data import zone_data_roots
from omega_serv.core.i18n import _
from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.domain.persistence.snapshots import (
    SnapshotMetadata,
    SnapshotStatus,
    create_snapshot_id,
)
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore
from omega_serv.ports.clock_port import ClockPort

ALLOWED_TOP_LEVEL = frozenset({"config", "secure", "var", "webroot", MANIFEST_NAME})
"""Seuls emplacements qu'une sauvegarde omega-serv contient (le contenu du site peut avoir un autre nom de webroot :
voir `extra_top_level`)."""
MAX_IMPORT_BYTES = 8 * 1024 * 1024 * 1024
MAX_MEMBERS = 200_000
CONFIG_MEMBER = "config/omega-serve.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class TransferResult:
    success: bool
    message: str
    path: Path | None = None
    snapshot_id: str | None = None


def export_backup(metadata_store: BackupMetadataStore, snapshot_id: str, dest_dir: Path,
                  instance_name: str) -> TransferResult:
    metadata = metadata_store.load(snapshot_id)
    if metadata is None or metadata.file_path is None or not Path(metadata.file_path).is_file():
        return TransferResult(False, _("Sauvegarde introuvable : {snapshot_id}").format(snapshot_id=snapshot_id))
    if not dest_dir.is_dir():
        return TransferResult(False, _("Dossier de destination introuvable : {path}").format(path=dest_dir))
    safe_instance = "".join(c if c.isalnum() or c in "-_." else "-" for c in instance_name) or "omega-serv"
    target = dest_dir / f"omega-serv-{safe_instance}-{snapshot_id}.tar.gz"
    sidecar = target.with_name(target.name + ".sha256")
    if target.exists() or sidecar.exists():
        return TransferResult(False, _("{path} existe déjà : rien n'a été écrasé.").format(path=target))
    try:
        # Scan de securite n° 2 (2026-11-20, F35) : cree 0600 AVANT d'y ecrire (peut contenir des cles TLS et
        # users.json) ; copyfile creait 0644 puis chmod apres coup, un autre compte pouvait l'ouvrir entre-temps.
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as destination, open(metadata.file_path, "rb") as source:
            shutil.copyfileobj(source, destination)
        sidecar.write_text(f"{sha256_of(target)}  {target.name}\n", encoding="utf-8")
    except OSError as exc:
        return TransferResult(False, _("Échec de l'export : {exc}").format(exc=exc))
    return TransferResult(True, _("Sauvegarde exportée : {path} (empreinte : {sidecar}).").format(
        path=target, sidecar=sidecar.name), path=target)


def _member_error(name: str, kind: str, extra_top_level: frozenset[str]) -> str | None:
    path = PurePosixPath(name)
    if path.is_absolute() or name.startswith("/"):
        return _("chemin absolu : {name}").format(name=name)
    if ".." in path.parts:
        return _("chemin qui remonte (..) : {name}").format(name=name)
    if kind == "other":
        return _("lien ou fichier spécial : {name}").format(name=name)
    top = path.parts[0] if path.parts else ""
    if top not in ALLOWED_TOP_LEVEL | extra_top_level:
        return _("emplacement inattendu : {name}").format(name=name)
    return None


def import_backup(archive_path: Path, archive_store: ArchiveStore, metadata_store: BackupMetadataStore,
                  clock: ClockPort, webroot_name: str = "webroot") -> TransferResult:
    sidecar = archive_path.with_name(archive_path.name + ".sha256")
    if not archive_path.is_file():
        return TransferResult(False, _("Fichier introuvable : {path}").format(path=archive_path))
    if archive_path.stat().st_size > MAX_IMPORT_BYTES:
        return TransferResult(False, _("Archive trop grosse pour être importée : {path}").format(path=archive_path))
    if not sidecar.is_file():
        return TransferResult(False, _("Empreinte absente : {sidecar} doit accompagner l'archive (créée par "
                                       "« Exporter »). Import refusé : l'intégrité ne peut pas être vérifiée.").format(
            sidecar=sidecar.name))
    expected = sidecar.read_text(encoding="utf-8").split()[:1]
    if not expected or expected[0].lower() != sha256_of(archive_path):
        return TransferResult(False, _("Empreinte fausse : l'archive a été modifiée ou abîmée. Import refusé."))
    try:
        members = archive_store.describe_members(archive_path)
    except ArchiveStoreError as exc:
        return TransferResult(False, str(exc))
    if len(members) > MAX_MEMBERS:
        return TransferResult(False, _("Archive refusée : trop de fichiers ({count}).").format(count=len(members)))
    extra_top = frozenset({PurePosixPath(webroot_name).parts[0]}) if webroot_name else frozenset()
    # Donnees des zones (2026-11-15) : dossiers du projet hors webroot que la configuration DE L'ARCHIVE designe
    # (alias, scripts FastCGI) - jamais un emplacement de l'installation (zone_data.INSTALLATION_NAMES).
    extra_top |= _archived_zone_roots(archive_store, archive_path)
    for name, kind, _size in members:
        error = _member_error(name, kind, extra_top)
        if error is not None:
            return TransferResult(False, _("Archive refusée, {error}.").format(error=error))
    if CONFIG_MEMBER not in {name for name, _kind, _size in members}:
        return TransferResult(False, _("Archive refusée : {member} absent, ce n'est pas une sauvegarde "
                                       "omega-serv.").format(member=CONFIG_MEMBER))
    manifest = read_manifest(archive_store, archive_path)
    now = clock.now()
    snapshot_id = create_snapshot_id(now)
    target = archive_store.base_dir / f"{snapshot_id}.tar.gz"
    try:
        archive_store.base_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive_path, target)
    except OSError as exc:
        return TransferResult(False, _("Échec de l'import : {exc}").format(exc=exc))
    metadata_store.save(SnapshotMetadata(
        snapshot_id=snapshot_id, created_at=now,
        scope=str(manifest.get("scope", "config")) if manifest else "config",
        description=_("importée de {name}").format(name=archive_path.name),
        app_version=str(manifest["app_version"]) if manifest and manifest.get("app_version") else None,
        status=SnapshotStatus.COMPLETED, file_path=str(target), file_size_bytes=target.stat().st_size,
    ))
    return TransferResult(True, _("Sauvegarde importée : {snapshot_id}. Elle est dans la liste ; la restaurer "
                                  "reste une étape à part.").format(snapshot_id=snapshot_id),
                          path=target, snapshot_id=snapshot_id)


def _archived_zone_roots(archive_store: ArchiveStore, archive_path: Path) -> frozenset[str]:
    try:
        raw = archive_store.read_member(archive_path, CONFIG_MEMBER)
        data = json.loads(raw) if raw else None
    except (ArchiveStoreError, ValueError):
        return frozenset()
    return zone_data_roots(data) if isinstance(data, dict) else frozenset()


def read_manifest(archive_store: ArchiveStore, archive_path: Path) -> dict[str, object] | None:
    try:
        raw = archive_store.read_member(archive_path, MANIFEST_NAME, max_bytes=64 * 1024)
        data = json.loads(raw) if raw else None
    except (ArchiveStoreError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@dataclass(frozen=True)
class ArchiveIdentity:
    bind: str | None
    port: int | None
    service_name: str | None
    app_version: str | None


def archive_identity(archive_store: ArchiveStore, archive_path: Path) -> ArchiveIdentity:
    """Adresse et port lus dans la configuration de l'archive (la source qui fait foi), nom du service et version
    dans sa fiche (absente des sauvegardes anterieures a la 3.0.0)."""
    manifest = read_manifest(archive_store, archive_path) or {}
    bind: str | None = None
    port: int | None = None
    try:
        raw = archive_store.read_member(archive_path, CONFIG_MEMBER)
        server = (json.loads(raw) or {}).get("server", {}) if raw else {}
        bind = str(server["bind"]) if "bind" in server else None
        port = int(server["port"]) if "port" in server else None
    except (ArchiveStoreError, ValueError, TypeError, AttributeError):
        pass
    service = manifest.get("service_name")
    version = manifest.get("app_version")
    return ArchiveIdentity(bind, port, str(service) if service else None, str(version) if version else None)


