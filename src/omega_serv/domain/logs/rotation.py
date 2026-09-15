# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regles pures de rotation des logs (plan interface §3.4/§8, port
adapte depuis omega-fire domain/logs/rotation.py). Trimme a la seule
strategie que `domain/config/entities.py::RotationConfig` sait
configurer (taille + nombre conserve) - fire propose aussi BY_AGE/
BY_COUNT/DAILY/WEEKLY/MONTHLY, mais rien cote SERV ne peut regler ces
strategies (RotationConfig n'a pas de champ pour), les porter aurait
ete du code mort (D-008)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class RotationPlan:
    log_path: Path
    should_rotate: bool
    reason: str = ""
    archive_name: str = ""
    rotations_to_delete: tuple[str, ...] = field(default_factory=tuple)


def generate_archive_name(log_path: Path, timestamp: datetime) -> str:
    """Nom d'archive : `{nom_du_log}.{horodatage}.tar.gz` (ArchiveStore
    enveloppe toujours en tar.gz, meme pour un fichier unique - voir
    infrastructure/storage/files/archive_store.py)."""
    timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S")
    return f"{log_path.name}.{timestamp_str}.tar.gz"


def compute_rotations_to_delete(existing_rotations: list[str], keep: int) -> list[str]:
    """`existing_rotations` triees de la plus ancienne a la plus
    recente. Retourne celles a supprimer pour respecter `keep`."""
    if len(existing_rotations) < keep:
        return []
    return existing_rotations[: len(existing_rotations) - keep + 1]


def plan_rotation(
    log_path: Path,
    file_size_bytes: int,
    max_size_bytes: int,
    keep: int,
    existing_rotations: list[str],
    now: datetime | None = None,
) -> RotationPlan:
    """Determine si `log_path` doit tourner (taille actuelle >=
    `max_size_bytes`) et, si oui, le plan complet (nom d'archive,
    anciennes rotations a supprimer pour respecter `keep`). Ne fait
    aucun I/O - l'execution reelle est deleguee a
    infrastructure/logging/log_rotator.py."""
    if now is None:
        now = datetime.now(timezone.utc)

    if file_size_bytes < max_size_bytes:
        return RotationPlan(log_path=log_path, should_rotate=False)

    return RotationPlan(
        log_path=log_path,
        should_rotate=True,
        reason=f"Taille actuelle ({file_size_bytes} octets) >= seuil ({max_size_bytes} octets)",
        archive_name=generate_archive_name(log_path, now),
        rotations_to_delete=tuple(compute_rotations_to_delete(existing_rotations, keep)),
    )
