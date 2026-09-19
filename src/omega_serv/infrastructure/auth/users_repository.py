"""Implementation reelle de UsersRepositoryPort - fichier JSON
(paths.auth_file), ecriture atomique (meme mecanisme que la
configuration principale)."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.domain.security.auth.entities import UserAccount
from omega_serv.domain.security.auth.exceptions import UsersFileError
from omega_serv.ports.filesystem_port import FilesystemPort

_SUPPORTED_VERSIONS = frozenset({1})


class JsonUsersRepository:
    def __init__(self, filesystem: FilesystemPort, path: Path):
        self._fs = filesystem
        self._path = path

    def load(self) -> tuple[UserAccount, ...]:
        if not self._fs.exists(self._path):
            return ()
        try:
            data = json.loads(self._fs.read_text(self._path))
        except json.JSONDecodeError as e:
            raise UsersFileError(f"JSON invalide dans {self._path} : {e}") from e
        if not isinstance(data, dict) or data.get("version") not in _SUPPORTED_VERSIONS:
            raise UsersFileError(f"{self._path} : version non supportee ou structure invalide")
        return tuple(
            UserAccount(username=item["username"], password_hash=item["password_hash"])
            for item in data.get("users", [])
        )

    def save(self, users: tuple[UserAccount, ...]) -> None:
        content = json.dumps(
            {"version": 1, "users": [{"username": u.username, "password_hash": u.password_hash} for u in users]},
            indent=2, ensure_ascii=False,
        ) + "\n"
        self._fs.make_directory(self._path.parent)
        self._fs.atomic_write_text(self._path, content)
        self._fs.set_file_mode(self._path, 0o600)
