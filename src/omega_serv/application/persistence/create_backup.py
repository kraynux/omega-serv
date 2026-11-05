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

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.domain.persistence.snapshots import (
    SnapshotMetadata,
    SnapshotStatus,
    create_snapshot_id,
)
from omega_serv.domain.security.active_defense.config import parse_active_defense_config
from omega_serv.domain.security.riposte.config import parse_riposte_config
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore
from omega_serv.ports.clock_port import ClockPort


@dataclass(frozen=True)
class BackupResult:
    success: bool
    message: str
    metadata: SnapshotMetadata | None = None
    skipped: tuple[str, ...] = ()
    """Elements demandes mais non archives, avec la raison (hors du projet) - affiches a l'utilisateur."""


@dataclass
class _Collected:
    files: list[Path] = field(default_factory=list)
    databases: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def add(self, path: Path, project_root: Path, label: str, *, database: bool = False) -> None:
        """Seulement un element DANS le projet (tout reste dans le dossier omega-serv) et present."""
        resolved = path if path.is_absolute() else project_root / path
        try:
            resolved.resolve().relative_to(project_root.resolve())
        except ValueError:
            self.skipped.append(_("{label} : hors du dossier omega-serv ({path}), non sauvegardé").format(label=label, path=path))
            return
        if not resolved.exists():
            return  # composant non configure ou jamais cree : rien a sauvegarder, pas une erreur
        (self.databases if database else self.files).append(resolved)


def _collect_sources(request: BackupRequest, config: OmegaServConfig, project_root: Path, config_file: Path) -> _Collected:
    collected = _Collected()
    if request.include_config and config_file.exists():
        # Toujours sauvegarde, meme hors du dossier (lancement avec --config ailleurs) : archive alors sous
        # son seul nom, comme avant - c'est le seul element accepte hors du projet.
        collected.files.append(config_file)
    if request.include_waf_rules:
        waf_option = config.options.get("waf")
        if waf_option is not None:
            waf_config = parse_waf_config(waf_option.settings)
            for rule_path in waf_config.rule_paths:
                collected.add(Path(rule_path), project_root, _("règles WAF"))
            collected.add(Path(waf_config.blocklist.path), project_root, _("blocklist"))
            # Listes de mots-cles et Magnet (2026-11-01) : des regles WAF a part entiere, jamais sauvegardees avant.
            for keyword_list in waf_config.keyword_lists:
                collected.add(Path(keyword_list.file), project_root, _("listes de mots-clés WAF"))
            magnet = waf_config.magnet
            if magnet.script:
                collected.add(Path(magnet.script), project_root, _("script Magnet"))
            collected.add(Path(magnet.paths.rules_dir), project_root, _("règles Magnet"))
            collected.add(Path(magnet.paths.blocklist_file), project_root, _("blocklist Magnet"))
        collected.add(Path(config.paths.waf_script), project_root, _("script WAF Lua"))
    if request.include_auth_zones:
        collected.add(Path(config.paths.auth_file), project_root, _("utilisateurs"))
        collected.add(Path(config.paths.auth_zones), project_root, _("zones Auth"))
    if request.include_certificates:
        collected.add(Path("secure") / "certificates", project_root, _("certificats"))
        for label, configured in (
            (_("certificat"), config.tls.certificate_path), (_("clé privée"), config.tls.private_key_path),
            (_("chaîne de certificats"), config.tls.chain_path),
        ):
            if configured and not Path(configured).is_relative_to("secure/certificates"):
                collected.add(Path(configured), project_root, label)
    if request.include_error_pages:
        error_pages = config.options.get("error_pages")
        custom_dir = str(error_pages.settings.get("custom_dir", "webroot/.errors")) if error_pages else "webroot/.errors"
        collected.add(Path(custom_dir), project_root, _("pages d'erreur personnalisées"))
    if request.include_preferences:
        collected.add(Path("var") / "settings.json", project_root, _("préférences"))
    if request.include_logs_library:
        for name in ("library.json", "favorites.json", "remote-log-sources.json"):
            collected.add(Path("var") / name, project_root, _("bibliothèque des journaux"))
        collected.add(Path("var") / "run" / "log_rotation_automations.json", project_root, _("rotations planifiées"))
    if request.include_active_defense:
        active_defense_option = config.options.get("active_defense")
        if active_defense_option is not None:
            active_defense_config = parse_active_defense_config(active_defense_option.settings)
            collected.add(Path(active_defense_config.storage.database), project_root, _("base Active Defense"), database=True)
    if request.include_riposte:
        riposte_option = config.options.get("riposte")
        riposte_config = parse_riposte_config(riposte_option.settings if riposte_option is not None else {})
        collected.add(Path(riposte_config.database), project_root, _("base RIPOSTE"), database=True)
    return collected


def _describe_scope(request: BackupRequest) -> str:
    flags = (
        (request.include_config, "config"), (request.include_waf_rules, "waf"), (request.include_auth_zones, "auth"),
        (request.include_certificates, "certificates"), (request.include_active_defense, "active_defense"),
        (request.include_error_pages, "error_pages"), (request.include_preferences, "preferences"),
        (request.include_logs_library, "logs_library"), (request.include_riposte, "riposte"),
    )
    return "+".join(name for included, name in flags if included)


def create_backup(
    request: BackupRequest,
    config: OmegaServConfig,
    project_root: Path,
    config_file: Path,
    archive_store: ArchiveStore,
    metadata_store: BackupMetadataStore,
    clock: ClockPort,
    snapshot: Callable[[Path, Path], None] | None = None,
) -> BackupResult:
    """`snapshot(base, copie)` : copie coherente d'une base en service (infrastructure/persistence/
    sqlite_snapshot.py, injectee - bootstrap ne doit jamais atteindre sqlite3). Sans elle, la base est
    archivee AVEC ses fichiers -wal et -shm (jamais le fichier principal seul)."""
    collected = _collect_sources(request, config, project_root, config_file)
    if not collected.files and not collected.databases:
        return BackupResult(False, _("Aucun composant sélectionné pour la sauvegarde."), skipped=tuple(collected.skipped))

    now = clock.now()
    snapshot_id = create_snapshot_id(now)
    archive_name = f"{snapshot_id}.tar.gz"
    staging = archive_store.base_dir / f".staging-{snapshot_id}"
    try:
        # Bases en service : copie coherente d'abord (jamais le fichier brut sans son -wal), archivee a
        # l'emplacement de la base - sauvegarde possible serveur en marche (decision utilisateur 2026-11-01).
        extra: list[tuple[Path, str]] = []
        for database in collected.databases:
            relative = database.resolve().relative_to(project_root.resolve())
            if snapshot is not None:
                copy = staging / relative
                snapshot(database, copy)
                extra.append((copy, str(relative)))
            else:
                collected.files.append(database)
                collected.files.extend(
                    sibling for sibling in (database.with_name(database.name + "-wal"), database.with_name(database.name + "-shm"))
                    if sibling.exists()
                )
        archive_path = archive_store.create_archive(
            archive_name, collected.files, base_path=project_root, extra_files=extra,
        )
    except (ArchiveStoreError, OSError) as exc:
        return BackupResult(False, _("Échec de la sauvegarde : {exc}").format(exc=exc), skipped=tuple(collected.skipped))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

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
    return BackupResult(
        True, _("Sauvegarde créée : {archive_name}.").format(archive_name=archive_name), metadata,
        skipped=tuple(collected.skipped),
    )
