"""Cas d'usage Bibliotheque de logs (gestion des logs, refonte menu
2026-10-15, porte depuis omega-log/plan_omega_log.md §3/§10) -
alimentation MANUELLE uniquement pour cette passe (voir docstring de
`domain/logs/library.py`)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.logs.library import LibraryRecord, LogFile
from omega_serv.ports.log_library_repository_port import LogLibraryRepositoryPort


def refresh_log_file(path: str, access: str = "file", service_id: str | None = None, note: str = "") -> LogFile:
    """Recalcule l'etat REEL (existe/taille/mtime) d'un chemin - jamais
    une donnee figee au moment d'un ajout anterieur (voir
    `LibraryRecord`). Appelee a chaque ouverture de la Bibliotheque."""
    try:
        stat = Path(path).stat()
    except OSError:
        return LogFile(path=path, access=access, service_id=service_id, exists=False, note=note)

    return LogFile(
        path=path, access=access, service_id=service_id, exists=True,
        size_bytes=stat.st_size, modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc), note=note,
    )


def list_library(repository: LogLibraryRepositoryPort) -> list[LogFile]:
    return [
        refresh_log_file(record.path, access=record.access, service_id=record.service_id)
        for record in repository.list_all()
    ]


def add_to_library(repository: LogLibraryRepositoryPort, log_file: LogFile) -> None:
    repository.add(LibraryRecord(path=log_file.path, access=log_file.access, service_id=log_file.service_id))


def add_many_to_library(repository: LogLibraryRepositoryPort, log_files: list[LogFile]) -> int:
    for log_file in log_files:
        add_to_library(repository, log_file)
    return len(log_files)


def remove_from_library(repository: LogLibraryRepositoryPort, path: str) -> None:
    repository.remove(path)
