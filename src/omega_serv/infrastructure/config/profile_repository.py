"""Implementation reelle de ProfileRepositoryPort - lit
config/profiles/*.json."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.domain.config.profile import Profile
from omega_serv.ports.filesystem_port import FilesystemPort


class FileProfileRepository:
    def __init__(self, filesystem: FilesystemPort, profiles_dir: Path):
        self._fs = filesystem
        self._profiles_dir = profiles_dir

    @property
    def custom_dir(self) -> Path:
        """Profils personnalises (2026-11-15) : etat de l'utilisateur, sauvegarde, reporte par migrate-state.sh,
        jamais livre par l'archive."""
        return self._profiles_dir / "custom"

    def list_profile_names(self) -> list[str]:
        """Profils fournis, puis personnalises (un nom personnalise ne reprend jamais un nom fourni)."""
        provided = [path.stem for path in self._fs.list_json_files(self._profiles_dir)]
        custom = ([path.stem for path in self._fs.list_json_files(self.custom_dir)]
                  if self._fs.is_dir(self.custom_dir) else [])
        return provided + [name for name in custom if name not in provided]

    def provided_profile_names(self) -> list[str]:
        return [path.stem for path in self._fs.list_json_files(self._profiles_dir)]

    def save_custom_profile(self, profile: Profile) -> Path:
        self._fs.make_directory(self.custom_dir)
        path = self.custom_dir / f"{profile.name}.json"
        self._fs.atomic_write_text(path, json.dumps(profile.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return path

    def delete_custom_profile(self, name: str) -> bool:
        path = self.custom_dir / f"{name}.json"
        if not self._fs.exists(path):
            return False
        self._fs.delete_file(path)
        return True

    def load_profile(self, name: str) -> Profile:
        path = self._profiles_dir / f"{name}.json"
        if not self._fs.exists(path):
            path = self.custom_dir / f"{name}.json"
        if not self._fs.exists(path):
            raise ProfileNotFoundError(name)
        try:
            raw = self._fs.read_text(path)
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            raise ProfileLoadError(_("Impossible de lire/parser {path} : {e}").format(path=path, e=e)) from e
        return Profile.from_dict(data)
