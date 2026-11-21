"""Fichiers de l'instance maitre et des instances suivies (tableau de bord web, lot 6 ; plan §7.3 et §9.2).

Tout sous `var/lib/admin/` : le processus d'administration (compte du service sous systemd) doit les ecrire
(appairage par code, essais, dernier appel, instance ajoutee depuis la page), et `secure/` est en lecture seule pour
lui. Dossier en 2770 et fichiers en 660 : le TUI et la CLI (utilisateur) et le service (groupe) lisent et ecrivent
tous les deux (meme piege que var/run/, voir application/services/pid_file.py).

- `maitre.json` (instance suivie) : le maitre accepte, avec le hache scrypt de son jeton ;
- `appairage.json` (instance suivie) : la fenetre d'appairage par code ouverte, s'il y en a une ;
- `identite.json` (maitre) : identifiant et nom de ce maitre, crees au premier besoin ;
- `instances.json` (maitre) : instances suivies (jeton en clair, empreinte epinglee) et sondes HTTP.

Un fichier illisible se lit comme absent (aucun maitre accepte = tout appel refuse ; aucune instance suivie) et n'est
jamais ecrase en silence par une lecture."""
from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from omega_serv.domain.admin_web.master import (
    AcceptedMaster,
    Fleet,
    FollowedInstance,
    MasterIdentity,
    PairingWindow,
    valid_master_id,
)
from omega_serv.ports.filesystem_port import FilesystemPort

ADMIN_STATE_RELATIVE_DIR = Path("var") / "lib" / "admin"
MASTER_RELATIVE_PATH = ADMIN_STATE_RELATIVE_DIR / "maitre.json"
PAIRING_RELATIVE_PATH = ADMIN_STATE_RELATIVE_DIR / "appairage.json"
IDENTITY_RELATIVE_PATH = ADMIN_STATE_RELATIVE_DIR / "identite.json"
FLEET_RELATIVE_PATH = ADMIN_STATE_RELATIVE_DIR / "instances.json"
SHARED_DIR_MODE = 0o2770
SHARED_FILE_MODE = 0o660


class _JsonFile:
    def __init__(self, filesystem: FilesystemPort, path: Path) -> None:
        self._fs = filesystem
        self.path = path

    def read(self) -> dict[str, Any] | None:
        try:
            if not self._fs.exists(self.path):
                return None
            data = json.loads(self._fs.read_text(self.path))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def write(self, data: dict[str, Any], *, compact: bool = False) -> None:
        directory = self.path.parent
        self._fs.make_directory(directory, mode=SHARED_DIR_MODE)
        with contextlib.suppress(OSError):  # dossier a l'autre compte : l'ecriture juste apres fait foi
            self._fs.set_file_mode(directory, SHARED_DIR_MODE)
        text = json.dumps(data, separators=(",", ":")) if compact else json.dumps(data, indent=2, ensure_ascii=False)
        self._fs.atomic_write_text(self.path, text + "\n", min_mode=SHARED_FILE_MODE)

    def remove(self) -> None:
        if self._fs.exists(self.path):
            self._fs.delete_file(self.path)


def _parse(data: dict[str, Any] | None, build: Callable[[dict[str, Any]], Any]) -> Any:
    if data is None:
        return None
    try:
        return build(data)
    except (KeyError, TypeError, ValueError):
        return None


class MasterStore:
    """Cote instance suivie : maitre accepte et fenetre d'appairage."""

    def __init__(self, filesystem: FilesystemPort, project_root: Path) -> None:
        self._master = _JsonFile(filesystem, project_root / MASTER_RELATIVE_PATH)
        self._pairing = _JsonFile(filesystem, project_root / PAIRING_RELATIVE_PATH)

    def load_master(self) -> AcceptedMaster | None:
        result: AcceptedMaster | None = _parse(self._master.read(), AcceptedMaster.from_dict)
        return result

    def save_master(self, master: AcceptedMaster | None) -> None:
        if master is None:
            self._master.remove()
        else:
            self._master.write(master.to_dict())

    def load_pairing(self) -> PairingWindow | None:
        result: PairingWindow | None = _parse(self._pairing.read(), PairingWindow.from_dict)
        return result

    def save_pairing(self, window: PairingWindow | None) -> None:
        if window is None:
            self._pairing.remove()
        else:
            self._pairing.write(window.to_dict())


class FleetStore:
    """Cote maitre : identite et instances suivies."""

    def __init__(self, filesystem: FilesystemPort, project_root: Path) -> None:
        self._identity = _JsonFile(filesystem, project_root / IDENTITY_RELATIVE_PATH)
        self._fleet = _JsonFile(filesystem, project_root / FLEET_RELATIVE_PATH)

    def identity(self, new_id: Callable[[], str], default_name: str) -> MasterIdentity:
        data = self._identity.read()
        if data is not None and valid_master_id(data.get("master_id")) and isinstance(data.get("name"), str):
            return MasterIdentity(data["master_id"], data["name"])
        identity = MasterIdentity(new_id(), default_name)
        self._identity.write(identity.to_dict())
        return identity

    def load(self) -> Fleet:
        data = self._fleet.read()
        if data is None or not isinstance(data.get("instances"), list):
            return Fleet()
        items: list[FollowedInstance] = []
        for raw in data["instances"]:
            item = _parse(raw, FollowedInstance.from_dict) if isinstance(raw, dict) else None
            if item is not None:
                items.append(item)
        return Fleet(tuple(items))

    def save(self, fleet: Fleet) -> None:
        self._fleet.write({"version": 1, "instances": [item.to_dict() for item in fleet.instances]})
