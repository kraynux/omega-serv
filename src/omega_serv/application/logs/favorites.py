"""Cas d'usage Favoris de logs (gestion des logs, refonte menu
2026-10-15, porte depuis omega-log/plan_omega_log.md §3) - un favori qui
violerait la regle de compatibilite viewer/nombre de logs (voir
`domain/logs/viewer_type.py::allowed_viewers`) est refuse a la
creation, jamais silencieusement tronque."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.logs.favorite import Favorite
from omega_serv.domain.logs.viewer_type import ViewerType, allowed_viewers
from omega_serv.ports.log_favorite_repository_port import LogFavoriteRepositoryPort


@dataclass
class CreateFavoriteResult:
    success: bool
    message: str = ""


def list_favorites(repository: LogFavoriteRepositoryPort) -> list[Favorite]:
    return repository.list_all()


def create_favorite(
    repository: LogFavoriteRepositoryPort, *, name: str, paths: list[str], viewer: ViewerType,
) -> CreateFavoriteResult:
    if not name.strip():
        return CreateFavoriteResult(success=False, message="Nom requis.")
    if not paths:
        return CreateFavoriteResult(success=False, message="Au moins un log est requis.")
    if viewer not in allowed_viewers(len(paths)):
        return CreateFavoriteResult(
            success=False,
            message=f"{len(paths)} log(s) selectionne(s) : seul {allowed_viewers(len(paths))[-1].value} est compatible.",
        )

    repository.add(Favorite(name=name.strip(), paths=tuple(paths), viewer=viewer))
    return CreateFavoriteResult(success=True, message=f"Favori '{name}' enregistre.")


def remove_favorite(repository: LogFavoriteRepositoryPort, name: str) -> None:
    repository.remove(name)
