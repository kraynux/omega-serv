# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
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
            # `remove_unit_file` (sudo) peut lever directement (meme
            # convention non-attrapee que install_systemd_service pour
            # write_unit_file/create_system_user/grant_directory_access,
            # cf. service_screen.py) - attrapee ICI specifiquement, car
            # cette fonction promet un UninstallInstanceResult structure,
            # jamais une exception qui laisserait le registre/repertoire
            # dans un etat ambigu.
            messages.append(str(e))
            return UninstallInstanceResult(False, "\n".join(messages))
        messages.append(uninstall_result.message)
        if not uninstall_result.success:
            # Etape privilegiee echouee (unite introuvable) : jamais
            # continuer vers le registre/repertoire, l'unite reste
            # installee - un etat partiel coherent, pas un abandon
            # silencieux au milieu d'une suppression de donnees.
            return UninstallInstanceResult(False, "\n".join(messages))

        still_used = check_account_still_in_use(
            filesystem, systemd_unit_dir, DEFAULT_SYSTEM_USER, entry.service_name,
        )
        remove_system_user = getattr(service_manager, "remove_system_user", None)
        if still_used is None and remove_system_user is not None:
            try:
                remove_system_user(DEFAULT_SYSTEM_USER, DEFAULT_SYSTEM_GROUP)
                messages.append(f"Compte systeme {DEFAULT_SYSTEM_USER!r} retire (plus reference par aucune autre instance).")
            except ServiceControlError as e:
                # Echec de nettoyage non bloquant : le compte reste, mais
                # l'unite de CETTE instance est deja retiree - continuer
                # vers le registre/repertoire plutot qu'abandonner une
                # desinstallation par ailleurs reussie pour un detail de
                # nettoyage secondaire.
                messages.append(f"Echec du retrait du compte systeme {DEFAULT_SYSTEM_USER!r} : {e}")
        elif still_used is not None:
            messages.append(f"Compte systeme {DEFAULT_SYSTEM_USER!r} conserve (encore utilise par {still_used!r}).")
    else:
        messages.append("Aucune unite systemd installee pour cette instance.")

    registry.save([e for e in registry.load() if e.path != entry.path])
    messages.append(f"Instance {entry.name!r} retiree du registre.")

    if delete_directory:
        try:
            filesystem.delete_directory(entry.path)
            messages.append(f"Repertoire {entry.path} supprime.")
        except OSError as e:
            messages.append(f"Echec de la suppression du repertoire {entry.path} : {e}")
            return UninstallInstanceResult(False, "\n".join(messages))
    else:
        messages.append(f"Repertoire {entry.path} conserve (suppression non demandee).")

    return UninstallInstanceResult(True, "\n".join(messages))
