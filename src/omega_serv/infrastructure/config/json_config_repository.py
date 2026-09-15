# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation concrete de ConfigurationPort - chargement/ecriture
JSON reels (spec §5.1 : JSON pour la premiere version, §5.3 : ecriture
atomique)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.exceptions import ConfigLoadError
from omega_serv.ports.filesystem_port import FilesystemPort


class JsonConfigRepository:
    """Implementation reelle de ports.configuration_port.ConfigurationPort."""

    def __init__(self, filesystem: FilesystemPort, backups_dir: Path):
        self._fs = filesystem
        self._backups_dir = backups_dir

    def load(self, path: Path) -> OmegaServConfig:
        if not self._fs.exists(path):
            raise ConfigLoadError(f"Fichier de configuration introuvable : {path}")
        try:
            raw = self._fs.read_text(path)
        except OSError as e:
            raise ConfigLoadError(f"Impossible de lire {path} : {e}") from e
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"JSON invalide dans {path} : {e}") from e
        if not isinstance(data, dict):
            raise ConfigLoadError(f"{path} ne contient pas un objet JSON a la racine")
        return OmegaServConfig.from_dict(data)

    def save(self, path: Path, config: OmegaServConfig) -> None:
        """N'effectue AUCUNE validation metier - le validateur doit
        avoir ete appele par le code appelant avant (application/
        config/validate_config.py)."""
        if self._fs.exists(path):
            self._backup_existing(path)

        content = json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n"
        # config/ peut ne pas encore exister sur un projet neuf (meme
        # fix que infrastructure/auth/*_repository.py::save()).
        self._fs.make_directory(path.parent)
        self._fs.atomic_write_text(path, content)

    def _backup_existing(self, path: Path) -> None:
        """Sauvegarde versionnee avant remplacement (spec §5.3 etape 7)."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_name = f"{path.name}.{timestamp}.bak"
        self._fs.copy_file(path, self._backups_dir / backup_name)
