"""Cas d'usage : desinstallation complete d'une instance (OMEGA-SERV_
PLAN-DETAILLE_MULTI_INSTANCE.md §8.5/§9 Phase E) - retire l'unite
systemd si presente (arret+desactivation d'abord, jamais un fichier
d'unite retire sous un process encore actif), le compte systeme dedie
SEULEMENT s'il n'est plus reference par aucune AUTRE instance installee
(angle mort §8.1), retire toujours l'entree du registre, et supprime le
repertoire SEULEMENT si demande explicitement (`delete_directory` -
jamais par defaut, confirmation forte cote UI, cf. instances_screen.py).

Ports uniquement (FilesystemPort/InstanceRegistryPort/ServiceManagerPort)
- aucun import direct de infrastructure/, contrairement a
create_instance.py : ce module reste donc importable directement depuis
interfaces.tui/ sans passer par le regime d'injection __main__.py-only
(meme categorie que build_users_repository/build_capability_scanner,
verifie via lint-imports)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.application.services.install_service import (
    check_account_still_in_use,
    uninstall_systemd_service,
)
from omega_serv.application.services.manage_service import disable_service, stop_service
from omega_serv.core.i18n import _
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.services.exceptions import ServiceControlError
from omega_serv.domain.services.systemd_unit import DEFAULT_SYSTEM_GROUP, DEFAULT_SYSTEM_USER
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.instance_registry_port import InstanceRegistryPort
from omega_serv.ports.service_manager_port import ServiceManagerPort


@dataclass(frozen=True)
class UninstallInstanceResult:
    success: bool
    message: str


def uninstall_instance(
    filesystem: FilesystemPort,
    registry: InstanceRegistryPort,
    service_manager: ServiceManagerPort | None,
    systemd_unit_dir: Path,
    *,
    entry: InstanceEntry,
    delete_directory: bool,
) -> UninstallInstanceResult:
    messages: list[str] = []
    unit_path = systemd_unit_dir / f"{entry.service_name}.service"

    if service_manager is not None and filesystem.exists(unit_path):
        messages.append(stop_service(service_manager, entry.service_name).message)
        messages.append(disable_service(service_manager, entry.service_name).message)
        try:
            uninstall_result = uninstall_systemd_service(filesystem, unit_path, service_manager)
        except ServiceControlError as e:
            messages.append(str(e))
            return UninstallInstanceResult(False, "\n".join(messages))
        messages.append(uninstall_result.message)
        if not uninstall_result.success:
            return UninstallInstanceResult(False, "\n".join(messages))

        still_used = check_account_still_in_use(
            filesystem, systemd_unit_dir, DEFAULT_SYSTEM_USER, entry.service_name,
        )
        remove_system_user = getattr(service_manager, "remove_system_user", None)
        if still_used is None and remove_system_user is not None:
            try:
                remove_system_user(DEFAULT_SYSTEM_USER, DEFAULT_SYSTEM_GROUP)
                messages.append(_("Compte système {DEFAULT_SYSTEM_USER!r} retiré (plus référence par aucune autre instance).").format(DEFAULT_SYSTEM_USER=DEFAULT_SYSTEM_USER))
            except ServiceControlError as e:
                messages.append(_("Échec du retrait du compte système {DEFAULT_SYSTEM_USER!r} : {e}").format(DEFAULT_SYSTEM_USER=DEFAULT_SYSTEM_USER, e=e))
        elif still_used is not None:
            messages.append(_("Compte système {DEFAULT_SYSTEM_USER!r} conservé (encore utilisé par {still_used!r}).").format(DEFAULT_SYSTEM_USER=DEFAULT_SYSTEM_USER, still_used=still_used))
    else:
        messages.append(_("Aucune unité systemd installée pour cette instance."))

    registry.save([e for e in registry.load() if e.path != entry.path])
    messages.append(_("Instance {name!r} retirée du registre.").format(name=entry.name))

    if delete_directory:
        try:
            filesystem.delete_directory(entry.path)
            messages.append(_("Répertoire {path} supprimé.").format(path=entry.path))
        except OSError as e:
            messages.append(_("Échec de la suppression du répertoire {path} : {e}").format(path=entry.path, e=e))
            return UninstallInstanceResult(False, "\n".join(messages))
    else:
        messages.append(_("Répertoire {path} conservé (suppression non demandée).").format(path=entry.path))

    return UninstallInstanceResult(True, "\n".join(messages))
