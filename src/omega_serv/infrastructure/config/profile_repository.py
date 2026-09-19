"""Implementation reelle de ProfileRepositoryPort - lit
config/profiles/*.json."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.domain.config.profile import Profile
from omega_serv.ports.filesystem_port import FilesystemPort


class FileProfileRepository:
    def __init__(self, filesystem: FilesystemPort, profiles_dir: Path):
        self._fs = filesystem
        self._profiles_dir = profiles_dir

    def list_profile_names(self) -> list[str]:
        return [path.stem for path in self._fs.list_json_files(self._profiles_dir)]

    def load_profile(self, name: str) -> Profile:
        path = self._profiles_dir / f"{name}.json"
        if not self._fs.exists(path):
            raise ProfileNotFoundError(name)
        try:
            raw = self._fs.read_text(path)
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            raise ProfileLoadError(f"Impossible de lire/parser {path} : {e}") from e
        return Profile.from_dict(data)
