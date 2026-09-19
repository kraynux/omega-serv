"""Implementation reelle de AuthZonesRepositoryPort - fichier JSON
(paths.auth_zones), ecriture atomique. Permissions forcees a 0600 comme
users.json : `allowed_users` y liste des noms d'utilisateurs valides en
clair - un fichier lisible par tous saperait la protection anti-
enumeration de domain/security/auth/authorize.py (temps de calcul
constant) en revelant les usernames valides directement sur disque."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.domain.security.auth.entities import AuthZone
from omega_serv.domain.security.auth.exceptions import AuthZonesFileError
from omega_serv.domain.security.auth.zones import parse_auth_zones
from omega_serv.ports.filesystem_port import FilesystemPort

_SUPPORTED_VERSIONS = frozenset({1})


class JsonAuthZonesRepository:
    def __init__(self, filesystem: FilesystemPort, path: Path):
        self._fs = filesystem
        self._path = path

    def load(self) -> tuple[AuthZone, ...]:
        if not self._fs.exists(self._path):
            return ()
        try:
            data = json.loads(self._fs.read_text(self._path))
        except json.JSONDecodeError as e:
            raise AuthZonesFileError(f"JSON invalide dans {self._path} : {e}") from e
        if not isinstance(data, dict) or data.get("version") not in _SUPPORTED_VERSIONS:
            raise AuthZonesFileError(f"{self._path} : version non supportee ou structure invalide")
        return tuple(parse_auth_zones(data.get("zones", [])))

    def save(self, zones: tuple[AuthZone, ...]) -> None:
        content = json.dumps(
            {
                "version": 1,
                "zones": [
                    {
                        "path_prefix": z.path_prefix, "realm": z.realm,
                        "allowed_users": list(z.allowed_users), "allow_methods": list(z.allow_methods),
                    }
                    for z in zones
                ],
            },
            indent=2, ensure_ascii=False,
        ) + "\n"
        self._fs.make_directory(self._path.parent)
        self._fs.atomic_write_text(self._path, content)
        self._fs.set_file_mode(self._path, 0o600)
