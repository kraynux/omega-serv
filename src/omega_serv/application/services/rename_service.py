# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Nom du service : controle du format et renommage guide (decisions de l'auteur du 2026-11-15, projets 3.0.0 §7.6
et §7.10).

Avant : le champ « Nom du service » etait enregistre a chaque frappe. Une faute de frappe, unite installee et serveur
en marche, faisait piloter par l'ecran une unite inexistante ; l'ancienne devenait orpheline pour le TUI, et
« Installer » creait une seconde unite pour le meme dossier et le meme port.

Desormais le nom ne change qu'apres validation, et si une unite de CETTE installation existe sous l'ancien nom, le
renommage est un enchainement explicite : arreter, desactiver, desinstaller l'ancienne ; installer la nouvelle ;
remettre son etat (activee au demarrage, en marche). Jamais deux unites pour le meme dossier."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from omega_serv.application.services.install_service import (
    check_for_name_hijack,
    install_systemd_service,
    uninstall_systemd_service,
)
from omega_serv.application.services.manage_service import (
    disable_service,
    enable_service,
    get_service_status,
    start_service,
    stop_service,
)
from omega_serv.core.i18n import _
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.service_name import SERVICE_NAME_MAX_LENGTH
from omega_serv.domain.services.service_name import SERVICE_NAME_PATTERN as _SERVICE_NAME
from omega_serv.domain.services.systemd_unit import SystemdUnitParams
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.service_manager_port import ServiceManagerPort


class _Outcome(Protocol):
    """_Outcome de manage_service comme de install_service (deux classes de meme forme)."""

    @property
    def success(self) -> bool: ...

    @property
    def message(self) -> str: ...


def validate_service_name(name: str) -> str | None:
    """Message d'erreur, ou None. Sous-ensemble prudent des noms d'unite systemd : minuscules, chiffres, « - », « _ »,
    « . », 64 caracteres au plus, jamais « .service » a la fin (ajoute par omega-serv)."""
    if not name:
        return _("Le nom du service ne peut pas être vide.")
    if len(name) > SERVICE_NAME_MAX_LENGTH:
        return _("Le nom du service fait {length} caractères : {maximum} au plus.").format(
            length=len(name), maximum=SERVICE_NAME_MAX_LENGTH)
    if name.endswith(".service"):
        return _("N'ajoutez pas « .service » : omega-serv l'ajoute lui-même.")
    if not _SERVICE_NAME.fullmatch(name):
        return _("Caractères permis : minuscules a-z, chiffres, « - », « _ » et « . » ; le nom commence par une "
                 "lettre ou un chiffre.")
    return None


@dataclass(frozen=True)
class RenamePlan:
    """Ce qui se passera a la validation, decide AVANT toute action (montre a l'utilisateur)."""

    kind: str
    """« same » (rien a faire), « name_only » (aucune unite de cette installation sous l'ancien nom : seul le nom
    change), « rename » (enchainement complet), « taken » (nom pris par une AUTRE installation : refus)."""
    old_name: str
    new_name: str
    other_directory: Path | None = None


def plan_rename(filesystem: FilesystemPort, systemd_unit_dir: Path, project_root: Path, old_name: str,
                new_name: str) -> RenamePlan:
    if new_name == old_name:
        return RenamePlan("same", old_name, new_name)
    other = check_for_name_hijack(filesystem, systemd_unit_dir, project_root, new_name)
    if other is not None:
        return RenamePlan("taken", old_name, new_name, other)
    old_unit = systemd_unit_dir / f"{old_name}.service"
    ours = filesystem.exists(old_unit) and check_for_name_hijack(
        filesystem, systemd_unit_dir, project_root, old_name) is None
    if ours and not filesystem.exists(systemd_unit_dir / f"{new_name}.service"):
        return RenamePlan("rename", old_name, new_name)
    return RenamePlan("name_only", old_name, new_name)


@dataclass(frozen=True)
class RenameResult:
    success: bool
    steps: tuple[str, ...]
    """Une ligne par etape faite, dans l'ordre (affichee a l'utilisateur)."""
    message: str


def rename_installed_service(
    filesystem: FilesystemPort,
    manager: ServiceManagerPort,
    systemd_unit_dir: Path,
    plan: RenamePlan,
    unit_params: Callable[[str], SystemdUnitParams],
    installing_user: str | None,
) -> RenameResult:
    """Enchainement du renommage (plan.kind == « rename »). S'arrete a la premiere etape qui echoue et dit ou."""
    old, new = plan.old_name, plan.new_name
    status = get_service_status(manager, old)
    was_active = isinstance(status, ServiceStatus) and status.active
    was_enabled = isinstance(status, ServiceStatus) and status.enabled
    steps: list[str] = []

    def failed(result: _Outcome, where: str) -> RenameResult:
        return RenameResult(False, tuple(steps), _("Renommage interrompu à l'étape « {step} » : {message}").format(
            step=where, message=result.message))

    sequence: list[tuple[bool, Callable[[], _Outcome], str]] = [
        (was_active, lambda: stop_service(manager, old), _("arrêter {name}").format(name=old)),
        (was_enabled, lambda: disable_service(manager, old), _("désactiver {name} au démarrage").format(name=old)),
        (True, lambda: uninstall_systemd_service(filesystem, systemd_unit_dir / f"{old}.service", manager),
         _("désinstaller l'unité {name}").format(name=old)),
        (True, lambda: install_systemd_service(filesystem, unit_params(new), systemd_unit_dir / f"{new}.service",
                                               manager, installing_user=installing_user),
         _("installer l'unité {name}").format(name=new)),
        (was_enabled, lambda: enable_service(manager, new), _("activer {name} au démarrage").format(name=new)),
        (was_active, lambda: start_service(manager, new), _("démarrer {name}").format(name=new)),
    ]
    for wanted, action, label in sequence:
        if not wanted:
            continue
        result = action()
        if not result.success:
            return failed(result, label)
        steps.append(label)
    return RenameResult(True, tuple(steps), _("Service renommé : {old} -> {new}.").format(old=old, new=new))
