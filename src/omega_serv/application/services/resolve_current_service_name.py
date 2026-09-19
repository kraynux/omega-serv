"""Nom du service systemd pilotant CETTE instance (repertoire projet
courant) - meme regle exacte que `service_screen.py::_service_name`
(instance enregistree en multi-instance en priorite, sinon le dernier
nom tape dans l'ecran SERVICE, sinon le nom par defaut), extraite ici
pour etre reutilisee par le bouton "Redemarrer maintenant" (retour
utilisateur, guide d'aide - point 4) sans dupliquer la resolution
d'instance dans un second ecran."""
from __future__ import annotations

from pathlib import Path

from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.instance_registry_port import InstanceRegistryPort
from omega_serv.ports.settings_store import SettingsStore

DEFAULT_SERVICE_NAME = "omega-serv"
SERVICE_NAME_SETTINGS_KEY = "service_name"


def resolve_current_service_name(
    instance_registry: InstanceRegistryPort,
    filesystem: FilesystemPort,
    settings_store: SettingsStore,
    project_root: Path,
) -> str:
    current_path = filesystem.resolve_real_path(project_root)
    for entry in instance_registry.load():
        if entry.path == current_path:
            return entry.service_name
    return settings_store.get(SERVICE_NAME_SETTINGS_KEY, "") or DEFAULT_SERVICE_NAME
