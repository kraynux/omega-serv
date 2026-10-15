"""Cas d'usage Sources distantes (SSH) de la Bibliotheque de logs
(OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md, 2026-10-15)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.logs.remote_source import RemoteLogSource
from omega_serv.ports.remote_log_source_repository_port import RemoteLogSourceRepositoryPort


@dataclass
class SaveRemoteSourceResult:
    success: bool
    message: str = ""


def list_remote_sources(repository: RemoteLogSourceRepositoryPort) -> list[RemoteLogSource]:
    return repository.list_all()


def save_remote_source(
    repository: RemoteLogSourceRepositoryPort, *,
    label: str, host: str, remote_path: str,
    user: str | None = None, port: int | None = None, identity_file: str | None = None,
) -> SaveRemoteSourceResult:
    if not label.strip():
        return SaveRemoteSourceResult(success=False, message="Label requis.")
    if not host.strip():
        return SaveRemoteSourceResult(success=False, message="Hote requis.")
    if not remote_path.strip():
        return SaveRemoteSourceResult(success=False, message="Chemin distant requis.")
    if port is not None and not (1 <= port <= 65535):
        return SaveRemoteSourceResult(success=False, message="Port invalide (1-65535).")

    repository.add(RemoteLogSource(
        label=label.strip(), host=host.strip(), remote_path=remote_path.strip(),
        user=user.strip() if user and user.strip() else None,
        port=port,
        identity_file=identity_file.strip() if identity_file and identity_file.strip() else None,
    ))
    return SaveRemoteSourceResult(success=True, message=f"Source '{label}' enregistree.")


def remove_remote_source(repository: RemoteLogSourceRepositoryPort, label: str) -> None:
    repository.remove(label)
