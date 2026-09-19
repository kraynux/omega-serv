"""Contrat de stockage d'un fichier uploade (spec §27)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from omega_serv.domain.upload.entities import UploadRequest


class UploadStoragePort(Protocol):
    def store(self, request: UploadRequest, storage_relative_path: str, content: bytes) -> Path:
        """Ecrit `content` sous la zone de stockage `storage_relative_path`
        (relative a la racine du projet) et retourne le chemin absolu
        reel du fichier ecrit. Le nom de fichier final est genere par
        l'implementation - jamais le nom fourni par le client
        (`request.filename`), voir plan corrige §5."""
        ...

    def count_and_size(self, storage_relative_path: str) -> tuple[int, int]:
        """Retourne (nombre de fichiers, taille totale en octets) deja
        presents sous la zone de stockage - utilise pour les quotas
        (plan corrige §6). (0, 0) si le repertoire n'existe pas encore."""
        ...
