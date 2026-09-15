# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : creer une sauvegarde de configuration (plan interface
§3.5/§10). Rassemble les fichiers reels selon les flags de
`BackupRequest`, les archive via `ArchiveStore` (deja porte en Phase VI)
avec `base_path=project_root` pour que les chemins relatifs soient
preserves dans l'archive (necessaire pour que la restauration
reecrive chaque fichier a son emplacement d'origine). Les sources
manquantes (WAF non configure, aucun certificat genere...) sont
silencieusement ignorees par `ArchiveStore.create_archive`, jamais une
erreur bloquante."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.domain.persistence.snapshots import (
    SnapshotMetadata,
    SnapshotStatus,
    create_snapshot_id,
)
from omega_serv.domain.security.active_defense.config import parse_active_defense_config
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore
from omega_serv.ports.clock_port import ClockPort


@dataclass(frozen=True)
class BackupResult:
    success: bool
    message: str
    metadata: SnapshotMetadata | None = None


def _collect_sources(request: BackupRequest, config: OmegaServConfig, project_root: Path, config_file: Path) -> list[Path]:
    sources: list[Path] = []
    if request.include_config:
        sources.append(config_file)
    if request.include_waf_rules:
        waf_option = config.options.get("waf")
        if waf_option is not None:
            waf_config = parse_waf_config(waf_option.settings)
            sources.extend(project_root / p for p in waf_config.rule_paths)
            sources.append(project_root / waf_config.blocklist.path)
    if request.include_auth_zones:
        sources.append(project_root / config.paths.auth_file)
        sources.append(project_root / config.paths.auth_zones)
    if request.include_certificates:
        sources.append(project_root / "secure" / "certificates")
    if request.include_active_defense:
        active_defense_option = config.options.get("active_defense")
        if active_defense_option is not None:
            active_defense_config = parse_active_defense_config(active_defense_option.settings)
            sources.append(project_root / active_defense_config.storage.database)
    return sources


def _describe_scope(request: BackupRequest) -> str:
    parts = []
    if request.include_config:
        parts.append("config")
    if request.include_waf_rules:
        parts.append("waf")
    if request.include_auth_zones:
        parts.append("auth")
    if request.include_certificates:
        parts.append("certificates")
    if request.include_active_defense:
        parts.append("active_defense")
    return "+".join(parts)


def create_backup(
    request: BackupRequest,
    config: OmegaServConfig,
    project_root: Path,
    config_file: Path,
    archive_store: ArchiveStore,
    metadata_store: BackupMetadataStore,
    clock: ClockPort,
) -> BackupResult:
    sources = _collect_sources(request, config, project_root, config_file)
    if not sources:
        return BackupResult(False, "Aucun composant selectionne pour la sauvegarde.")

    now = clock.now()
    snapshot_id = create_snapshot_id(now)
    archive_name = f"{snapshot_id}.tar.gz"

    try:
        archive_path = archive_store.create_archive(archive_name, sources, base_path=project_root)
    except ArchiveStoreError as exc:
        return BackupResult(False, f"Echec de la sauvegarde : {exc}")

    metadata = SnapshotMetadata(
        snapshot_id=snapshot_id,
        created_at=now,
        scope=_describe_scope(request),
        description=request.description,
        status=SnapshotStatus.COMPLETED,
        file_path=str(archive_path),
        file_size_bytes=archive_path.stat().st_size,
    )
    metadata_store.save(metadata)
    return BackupResult(True, f"Sauvegarde creee : {archive_name}.", metadata)
