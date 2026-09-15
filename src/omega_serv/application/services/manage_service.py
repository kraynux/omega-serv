# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `omega-serv service start/stop/restart/enable/disable/status`
(spec §24.2). Traduit les exceptions du domaine en resultat structure -
meme patron que manage_users.py/manage_zones.py/manage_blocklist.py."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import (
    ServiceControlError,
    ServiceNotFoundError,
    ServiceStatusError,
)
from omega_serv.ports.service_manager_port import ServiceManagerPort


@dataclass(frozen=True)
class ManageServiceResult:
    success: bool
    message: str


def _control(manager: ServiceManagerPort, service_name: str, operation: str, verb_past: str) -> ManageServiceResult:
    method = getattr(manager, operation)
    try:
        method(service_name)
    except ServiceNotFoundError as e:
        return ManageServiceResult(False, str(e))
    except ServiceControlError as e:
        return ManageServiceResult(False, str(e))
    return ManageServiceResult(True, f"Service {service_name!r} {verb_past}.")


def start_service(manager: ServiceManagerPort, service_name: str) -> ManageServiceResult:
    return _control(manager, service_name, "start", "demarre")


def stop_service(manager: ServiceManagerPort, service_name: str) -> ManageServiceResult:
    return _control(manager, service_name, "stop", "arrete")


def restart_service(manager: ServiceManagerPort, service_name: str) -> ManageServiceResult:
    return _control(manager, service_name, "restart", "redemarre")


def reload_service(manager: ServiceManagerPort, service_name: str) -> ManageServiceResult:
    # Retour utilisateur 2026-09-11 : distinct de restart_service -
    # garde les connexions actives, ne fait que relire la config deja
    # codee cote applicatif (SIGHUP) ; echoue proprement si l'unite
    # n'a pas ExecReload= (systemd) ou l'equivalent (OpenRC/runit).
    return _control(manager, service_name, "reload", "recharge")


def enable_service(manager: ServiceManagerPort, service_name: str) -> ManageServiceResult:
    return _control(manager, service_name, "enable", "active au demarrage")


def disable_service(manager: ServiceManagerPort, service_name: str) -> ManageServiceResult:
    return _control(manager, service_name, "disable", "desactive au demarrage")


def get_service_status(manager: ServiceManagerPort, service_name: str) -> ServiceStatus | ManageServiceResult:
    try:
        return manager.status(service_name)
    except (ServiceNotFoundError, ServiceStatusError) as e:
        return ManageServiceResult(False, str(e))
