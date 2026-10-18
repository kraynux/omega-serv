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


def resolve_current_service_account(
    instance_registry: InstanceRegistryPort,
    filesystem: FilesystemPort,
    settings_store: SettingsStore,
    project_root: Path,
    systemd_unit_dir: Path,
) -> str | None:
    """Compte systeme qui lit REELLEMENT les fichiers de CETTE instance
    (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.7, regle R3/R9) : la
    valeur `User=` de son unite systemd installee. None si aucune unite
    n'est installee (serveur lance a la main, sous le compte de
    l'utilisateur : rien a verifier)."""
    from omega_serv.domain.services.systemd_unit import service_user_from_unit

    service_name = resolve_current_service_name(instance_registry, filesystem, settings_store, project_root)
    unit_path = systemd_unit_dir / f"{service_name}.service"
    if not filesystem.exists(unit_path):
        return None
    try:
        return service_user_from_unit(filesystem.read_text(unit_path))
    except OSError:
        return None
