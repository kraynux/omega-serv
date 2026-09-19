"""Exceptions du sous-domaine logs/archives - vivent ici (pas dans
infrastructure/storage/files/archive_store.py qui les leve) pour rester
importables depuis interfaces.tui/ sans jamais toucher infrastructure/
directement, meme precedent que domain/security/tls/exceptions.py::
CertificateToolError."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class ArchiveStoreError(OmegaServError):
    pass
