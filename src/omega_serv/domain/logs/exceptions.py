"""Exceptions du sous-domaine logs/archives - vivent ici (pas dans
infrastructure/storage/files/archive_store.py qui les leve) pour rester
importables depuis interfaces.tui/ sans jamais toucher infrastructure/
directement, meme precedent que domain/security/tls/exceptions.py::
CertificateToolError."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class ArchiveStoreError(OmegaServError):
    pass


class LogPermissionError(OmegaServError):
    """Log illisible par le compte de l'interface (Statistiques, Voir et traiter IP). Depuis le 2026-11-07,
    l'ecran demande alors le mot de passe sudo et relit le log avec sudo ; sinon il affiche le chemin en cause."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path
