# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""`omega-serv synchro groupe-service ajouter|retirer` (2026-11-10, lot E de l'etape 3 d'omega-connect,
~/DEV/CONNECT/SPEC_ETAPE3_OMEGA_CONNECT_PLOMBERIE.md §5 et §14).

Donne au service de CETTE instance le groupe de la zone neutre (`omega-synchro`), pour qu'il puisse la lire
(journal des bans, etape 4). Decision de l'auteur : un complement systemd
`/etc/systemd/system/<service>.service.d/omega-synchro.conf` (`SupplementaryGroups=omega-synchro`) plutot qu'une
reecriture de l'unite : l'unite generee par `service install` n'est jamais touchee, et le retrait est exact.
omega-connect le demande et le verifie, il ne l'ecrit jamais lui-meme. Pris en compte au prochain redemarrage du
service."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from omega_lib.synchro.constants import ZONE_GROUP
from omega_lib.synchro.service_group import DROP_IN_NAME, drop_in_text, grants_zone_group

from omega_serv.application.services.install_service import ManageServiceResult
from omega_serv.core.i18n import _
from omega_serv.domain.services.systemd_unit import find_name_hijack
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.service_manager_port import ServiceManagerPort


def _paths(unit_dir: Path, service_name: str) -> tuple[Path, Path, Path]:
    unit_path = unit_dir / f"{service_name}.service"
    directory = unit_dir / f"{service_name}.service.d"
    return unit_path, directory, directory / DROP_IN_NAME


def zone_group_present(filesystem: FilesystemPort, unit_dir: Path, service_name: str) -> bool:
    _unit, _directory, path = _paths(unit_dir, service_name)
    try:
        return filesystem.is_file(path) and grants_zone_group(filesystem.read_text(path))
    except OSError:
        return False


def add_zone_group(
    filesystem: FilesystemPort,
    service_manager: ServiceManagerPort,
    unit_dir: Path,
    service_name: str,
    project_root: Path,
    group_exists: Callable[[str], bool],
) -> ManageServiceResult:
    unit_path, directory, path = _paths(unit_dir, service_name)
    if not filesystem.is_file(unit_path):
        return ManageServiceResult(False, _("Unité introuvable : {unit_path}").format(unit_path=unit_path))
    try:
        other_root = find_name_hijack({unit_path.name: filesystem.read_text(unit_path)}, project_root, service_name)
    except OSError as error:
        return ManageServiceResult(False, _("Unité illisible : {unit_path} ({error})").format(
            unit_path=unit_path, error=error))
    if other_root is not None:
        return ManageServiceResult(False, _(
            "Le service {service} appartient à une autre installation ({root}) : rien n'est modifié.").format(
            service=service_name, root=other_root))
    if not group_exists(ZONE_GROUP):
        return ManageServiceResult(False, _(
            "Le groupe {group} n'existe pas : établissez d'abord la zone neutre (omega-connect etablir). "
            "Sans lui, le service ne démarrerait plus.").format(group=ZONE_GROUP))
    if zone_group_present(filesystem, unit_dir, service_name):
        return ManageServiceResult(True, _("Le service {service} a déjà le groupe {group} ({path}).").format(
            service=service_name, group=ZONE_GROUP, path=path))
    write_drop_in = getattr(service_manager, "write_drop_in", None)
    if write_drop_in is None:
        return ManageServiceResult(False, _("Ce gestionnaire de service ne supporte pas cette opération."))
    write_drop_in(directory, path, drop_in_text())
    reload_daemon = getattr(service_manager, "reload_daemon", None)
    if reload_daemon is not None:
        reload_daemon()
    return ManageServiceResult(True, _(
        "Groupe {group} donné au service {service} ({path}). Pris en compte au prochain redémarrage du "
        "service (omega-serv service restart --service-name {service}).").format(
        group=ZONE_GROUP, service=service_name, path=path))


def remove_zone_group(
    filesystem: FilesystemPort,
    service_manager: ServiceManagerPort,
    unit_dir: Path,
    service_name: str,
) -> ManageServiceResult:
    _unit, directory, path = _paths(unit_dir, service_name)
    if not filesystem.exists(path):
        return ManageServiceResult(True, _("Le service {service} n'a pas le groupe {group} : rien à retirer.").format(
            service=service_name, group=ZONE_GROUP))
    remove_drop_in = getattr(service_manager, "remove_drop_in", None)
    if remove_drop_in is None:
        return ManageServiceResult(False, _("Ce gestionnaire de service ne supporte pas cette opération."))
    remove_drop_in(directory, path)
    reload_daemon = getattr(service_manager, "reload_daemon", None)
    if reload_daemon is not None:
        reload_daemon()
    return ManageServiceResult(True, _(
        "Groupe {group} retiré du service {service}. Pris en compte au prochain redémarrage du service.").format(
        group=ZONE_GROUP, service=service_name))
