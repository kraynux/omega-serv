"""Favori de la Bibliotheque de logs (gestion des logs, refonte menu
2026-10-15, porte depuis omega-log/plan_omega_log.md §3) : un ou
plusieurs logs + un viewer, enregistres sous un nom pour un lancement
direct depuis l'ecran Favoris."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.logs.viewer_type import ViewerType


@dataclass(frozen=True, slots=True)
class Favorite:
    name: str
    paths: tuple[str, ...]
    viewer: ViewerType
