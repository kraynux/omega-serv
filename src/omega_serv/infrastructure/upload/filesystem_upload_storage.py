# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation reelle de UploadStoragePort - ecriture sur disque via
FilesystemPort (jamais pathlib directement, meme discipline que les
autres repositories infrastructure/, voir infrastructure/auth/
users_repository.py)."""
from __future__ import annotations

import secrets
from pathlib import Path

from omega_serv.domain.upload.entities import UploadRequest
from omega_serv.ports.filesystem_port import FilesystemPort

_STORED_NAME_RANDOM_BYTES = 16


class FilesystemUploadStorage:
    def __init__(self, filesystem: FilesystemPort, project_root: Path):
        self._fs = filesystem
        self._project_root = project_root

    def store(self, request: UploadRequest, storage_relative_path: str, content: bytes) -> Path:
        # Nom de stockage genere, jamais le nom fourni par le client
        # directement comme nom de fichier final - meme si
        # validate_filename() l'a deja valide, un second niveau de
        # defense (nom aleatoire + extension conservee) evite les
        # collisions entre deux clients uploadant un fichier de meme nom
        # au meme instant.
        extension = "." + request.filename.rsplit(".", 1)[-1] if "." in request.filename else ""
        stored_name = f"{secrets.token_hex(_STORED_NAME_RANDOM_BYTES)}{extension}"

        storage_dir = self._project_root / storage_relative_path
        self._fs.make_directory(storage_dir)
        target = storage_dir / stored_name
        self._fs.write_bytes(target, content)
        return target

    def count_and_size(self, storage_relative_path: str) -> tuple[int, int]:
        storage_dir = self._project_root / storage_relative_path
        count = 0
        total_size = 0
        for name in self._fs.list_directory_entries(storage_dir):
            path = storage_dir / name
            if self._fs.is_file(path):
                count += 1
                total_size += self._fs.file_size(path)
        return count, total_size
