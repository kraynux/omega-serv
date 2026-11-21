"""Fichier des comptes de l'administration web : `secure/auth/admin-web.json` (tableau de bord web, lot 3).

Range a cote des comptes du site (secure/auth/), dont le partage avec le compte du service est deja en place et
repare par « Reparer les permissions » (application/services/install_service.py) : ecrit par l'utilisateur du TUI
ou de la CLI, relu par le service. Meme regle que users_repository.py : ecriture atomique, mode 0640 (groupe en
lecture, jamais « other »). Le service ne l'ecrit jamais (secure/ est en lecture seule sous systemd)."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.ports.filesystem_port import FilesystemPort

ACCOUNTS_RELATIVE_PATH = Path("secure") / "auth" / "admin-web.json"
_VERSION = 1


class AdminAccountsFileError(Exception):
    pass


class JsonAdminAccountsRepository:
    def __init__(self, filesystem: FilesystemPort, path: Path) -> None:
        self._fs = filesystem
        self._path = path

    def load(self) -> tuple[AdminAccount, ...]:
        if not self._fs.exists(self._path):
            return ()
        try:
            data = json.loads(self._fs.read_text(self._path))
            if not isinstance(data, dict) or data.get("version") != _VERSION:
                raise AdminAccountsFileError(_("{path} : version non supportée ou structure invalide").format(
                    path=self._path))
            return tuple(AdminAccount.from_dict(item) for item in data.get("accounts", []))
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise AdminAccountsFileError(_("{path} illisible : {error}").format(path=self._path, error=error)) from error

    def save(self, accounts: tuple[AdminAccount, ...]) -> None:
        content = json.dumps({"version": _VERSION, "accounts": [a.to_dict() for a in accounts]},
                             indent=2, ensure_ascii=False) + "\n"
        self._fs.make_directory(self._path.parent)
        self._fs.atomic_write_text(self._path, content)
        self._fs.set_file_mode(self._path, 0o640)
