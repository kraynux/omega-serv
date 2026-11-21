"""Codes de secours TOTP deja utilises (tableau de bord web, lot 3) : `var/lib/admin/used-backup-codes.json`.

Ecrit par le service (seul var/ lui est ouvert en ecriture) : le fichier des comptes (secure/auth/) reste en lecture
seule pour lui. On garde le hache du code utilise, jamais le code lui-meme. Une liste illisible est traitee comme vide
pour la lecture mais n'est jamais ecrasee en silence : l'ecriture suivante la remplace par une liste valide."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.ports.filesystem_port import FilesystemPort

USED_BACKUP_CODES_RELATIVE_PATH = Path("var") / "lib" / "admin" / "used-backup-codes.json"


class UsedBackupCodes:
    def __init__(self, filesystem: FilesystemPort, path: Path) -> None:
        self._fs = filesystem
        self._path = path

    def load(self) -> set[str]:
        if not self._fs.exists(self._path):
            return set()
        try:
            data = json.loads(self._fs.read_text(self._path))
        except (json.JSONDecodeError, OSError):
            return set()
        return {str(item) for item in data} if isinstance(data, list) else set()

    def add(self, code_hash: str) -> None:
        used = self.load() | {code_hash}
        self._fs.make_directory(self._path.parent)
        self._fs.atomic_write_text(self._path, json.dumps(sorted(used)) + "\n")
        self._fs.set_file_mode(self._path, 0o660)
