# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : tourner un log si necessaire (plan interface §3.4/§8).
Construit le plan via domain/logs/rotation.py (pur) puis l'execute
reellement : archive le fichier courant (ArchiveStore), supprime les
rotations les plus anciennes au-dela de `keep`, recree un fichier vide
pour que le logger continue d'ecrire dedans."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.logs.rotation import plan_rotation
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class RotateLogResult:
    success: bool
    message: str


def rotate_log_if_needed(
    log_path: Path,
    max_size_bytes: int,
    keep: int,
    filesystem: FilesystemPort,
    archive_store: ArchiveStore,
    now: datetime | None = None,
) -> RotateLogResult:
    if now is None:
        now = datetime.now(timezone.utc)
    if not filesystem.exists(log_path):
        return RotateLogResult(False, f"Log introuvable : {log_path}")

    size = filesystem.file_size(log_path)
    existing = sorted(p.name for p in archive_store.list_archives(f"{log_path.name}.*.tar.gz"))
    plan = plan_rotation(log_path, size, max_size_bytes, keep, existing, now)

    if not plan.should_rotate:
        return RotateLogResult(False, f"Rotation non necessaire ({size} octets < seuil {max_size_bytes} octets).")

    archive_store.create_archive(plan.archive_name, [log_path])
    for old_name in plan.rotations_to_delete:
        archive_store.delete_archive(archive_store.base_dir / old_name)
    filesystem.write_text(log_path, "")

    message = f"Log tourne : {plan.archive_name}."
    if plan.rotations_to_delete:
        message += f" {len(plan.rotations_to_delete)} ancienne(s) rotation(s) supprimee(s)."
    return RotateLogResult(True, message)
