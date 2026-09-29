"""Implementation reelle de UsersRepositoryPort - fichier JSON
(paths.auth_file), ecriture atomique (meme mecanisme que la
configuration principale).

Permissions 0640, pas 0600 (2026-09-29, retour utilisateur/incident reel
: boucle de crash systemd, `journalctl` montrant `PermissionError:
[Errno 13] Permission denied: '.../secure/auth/zones.json'`) : ce
fichier (et zones.json, meme regle) est ecrit par l'ecran
Authentification (interfaces/tui/screens/auth_menu_screen.py), donc par
l'UTILISATEUR INTERACTIF qui lance le TUI, mais relu par le SERVICE
systemd (compte systeme DEDIE, jamais le meme compte - voir
domain/services/systemd_unit.py) a chaque demarrage
(application/config/validate_config.py::_validate_auth_environment) -
avec l'ancien mode 0600 (proprietaire seul), le service n'a alors
litteralement AUCUN moyen de le lire, quel que soit l'etat de
`ReadWritePaths=`/`UMask=`/`grant_directory_access` (tous deja corrects
par ailleurs, aucun rapport avec la sandbox systemd ou les permissions
Unix classiques du DOSSIER - le fichier LUI-MEME l'interdisait). Meme
famille de bug DEJA rencontree et corrigee pour les logs (FileLineLogger,
2026-09-14) et le fichier PID (pid_file.py, 2026-09-27) : compte dedie
vs compte interactif partageant un meme repertoire. 0640 (groupe en
lecture, jamais "other") prolonge exactement la meme protection anti-
enumeration qu'avant (domain/security/auth/authorize.py, noms
d'utilisateurs jamais lisibles par un tiers sur la machine) tout en
autorisant le SEUL compte cense le lire - `secure/auth/` a ete ajoute au
perimetre de `grant_directory_access()` (application/services/
install_service.py) pour que le dossier LUI-MEME soit aussi partage
avec le groupe dedie (setgid inclus, memes fichiers herites au bon
groupe des leur creation)."""
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
        self._fs.set_file_mode(self._path, 0o640)
