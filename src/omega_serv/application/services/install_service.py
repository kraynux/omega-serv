"""Cas d'usage `omega-serv service install/uninstall` (spec §24.3/24.4 -
confirmation demandee par le CLI avant d'installer/supprimer, pas ici).
Perimetre systemd uniquement en V1 : OpenRC/runit n'ont pas de fichier
d'unite genere de la meme maniere (scripts rc.d/sv geres manuellement,
hors perimetre "generation d'unite durcie" du plan de developpement §5).

Ecriture/suppression de l'unite (plan interface §3.6, 2026-09-08) :
delegeree a `service_manager.write_unit_file`/`remove_unit_file`
lorsqu'elles existent (systemd uniquement, elevation `sudo` ponctuelle
geree dans l'adaptateur - voir infrastructure/services/
systemd_service_manager.py), avec repli sur FilesystemPort sinon (tests
avec un double simple qui n'implemente pas ces methodes) - jamais
`filesystem.atomic_write_text` en direct pour `/etc/systemd/system/`,
qui echouerait silencieusement en permission refusee sans elevation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.services.systemd_unit import (
    SystemdUnitParams,
    find_account_in_use,
    find_conflicting_unit,
    find_name_hijack,
    generate_systemd_unit,
)
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.service_manager_port import ServiceManagerPort


@dataclass(frozen=True)
class ManageServiceResult:
    success: bool
    message: str


def _read_installed_units(filesystem: FilesystemPort, systemd_unit_dir: Path) -> dict[str, str]:
    if not filesystem.is_dir(systemd_unit_dir):
        return {}
    unit_contents: dict[str, str] = {}
    for name in filesystem.list_directory_entries(systemd_unit_dir):
        if not name.endswith(".service"):
            continue
        path = systemd_unit_dir / name
        if not filesystem.is_file(path):
            continue
        try:
            unit_contents[name] = filesystem.read_text(path)
        except OSError:
            continue
    return unit_contents


def check_for_conflicting_unit(
    filesystem: FilesystemPort, systemd_unit_dir: Path, project_root: Path, exclude_service_name: str
) -> str | None:
    """Lit les unites deja presentes sous `systemd_unit_dir` (lecture
    seule, aucun privilege requis - 755/644 par defaut sous
    /etc/systemd/system/, le chemin reel passe par l'appelant - meme
    convention que `unit_path` pour install/uninstall, jamais code en
    dur ici) pour detecter une AUTRE unite pointant deja vers ce meme
    repertoire projet, avant d'en installer une nouvelle - voir
    `find_conflicting_unit` (domain) pour le detail du pourquoi (retour
    utilisateur 2026-09-10)."""
    unit_contents = _read_installed_units(filesystem, systemd_unit_dir)
    return find_conflicting_unit(unit_contents, project_root, exclude_service_name)


def check_for_name_hijack(
    filesystem: FilesystemPort, systemd_unit_dir: Path, project_root: Path, service_name: str
) -> Path | None:
    """Sens inverse de `check_for_conflicting_unit`, meme conversation
    2026-09-10 : detecte si `service_name` est deja utilise par une
    unite pointant vers un AUTRE repertoire - installer ici volerait
    silencieusement le nom (voir `find_name_hijack`, domain, pour le
    detail)."""
    unit_contents = _read_installed_units(filesystem, systemd_unit_dir)
    return find_name_hijack(unit_contents, project_root, service_name)


def check_account_still_in_use(
    filesystem: FilesystemPort, systemd_unit_dir: Path, user: str, exclude_service_name: str
) -> str | None:
    """OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §8.1/§9 Phase E -
    lecture seule, meme regime que `check_for_conflicting_unit`/
    `check_for_name_hijack` : voir `find_account_in_use` (domain) pour
    le detail du pourquoi."""
    unit_contents = _read_installed_units(filesystem, systemd_unit_dir)
    return find_account_in_use(unit_contents, user, exclude_service_name)


def install_systemd_service(
    filesystem: FilesystemPort,
    params: SystemdUnitParams,
    unit_path: Path,
    service_manager: ServiceManagerPort,
    installing_user: str | None = None,
) -> ManageServiceResult:
    create_system_user = getattr(service_manager, "create_system_user", None)
    if create_system_user is not None:
        create_system_user(params.user, params.group)

    grant_directory_access = getattr(service_manager, "grant_directory_access", None)
    if grant_directory_access is not None and installing_user is not None:
        grant_directory_access(params.project_root / "var", params.group, installing_user)

    content = generate_systemd_unit(params)

    write_unit_file = getattr(service_manager, "write_unit_file", None)
    if write_unit_file is not None:
        write_unit_file(unit_path, content)
    else:
        filesystem.atomic_write_text(unit_path, content)

    reload_daemon = getattr(service_manager, "reload_daemon", None)
    if reload_daemon is not None:
        reload_daemon()

    user_note = f" (compte systeme {params.user!r} cree ou deja present)" if create_system_user is not None else ""
    group_note = ""
    if grant_directory_access is not None and installing_user is not None:
        group_note = (
            f" - {installing_user!r} ajoute au groupe {params.group!r} : "
            "reconnectez votre session (ou 'newgrp " + params.group + "') pour que "
            "l'interface puisse lire ce que le service ecrit"
        )
    return ManageServiceResult(True, f"Unite installee : {unit_path}{user_note}{group_note}")


def uninstall_systemd_service(
    filesystem: FilesystemPort,
    unit_path: Path,
    service_manager: ServiceManagerPort,
) -> ManageServiceResult:
    if not filesystem.exists(unit_path):
        return ManageServiceResult(False, f"Unite introuvable : {unit_path}")

    remove_unit_file = getattr(service_manager, "remove_unit_file", None)
    if remove_unit_file is not None:
        remove_unit_file(unit_path)
    else:
        filesystem.delete_file(unit_path)

    reload_daemon = getattr(service_manager, "reload_daemon", None)
    if reload_daemon is not None:
        reload_daemon()

    return ManageServiceResult(True, f"Unite retiree : {unit_path}")
