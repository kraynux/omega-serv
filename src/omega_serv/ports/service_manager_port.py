# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de gestion de service (spec §24). Adapte depuis
omega-fire's `ServiceManager` (ABC) vers un Protocol - convention
OMEGA-SERV deja utilisee partout ailleurs (WafPort, CertificateToolPort,
FastCgiClientPort...), jamais d'ABC dans ce projet."""
from __future__ import annotations

from typing import Literal, Protocol

from omega_serv.domain.services.entities import ServiceStatus

ServiceManagerType = Literal["systemd", "openrc", "runit"]


class ServiceManagerPort(Protocol):
    def manager_type(self) -> ServiceManagerType:
        ...

    def start(self, service_name: str) -> bool:
        ...

    def stop(self, service_name: str) -> bool:
        ...

    def restart(self, service_name: str) -> bool:
        ...

    def reload(self, service_name: str) -> bool:
        """Rechargement a chaud du service (retour utilisateur
        2026-09-11) - distinct de `restart` : garde les connexions
        actives, ne fait que relire la configuration deja code cote
        applicatif (SIGHUP). Jamais un equivalent de `reload_daemon()`
        (systemd-only, relit les FICHIERS d'unite - pas dans ce
        Protocol, voir systemd_service_manager.py)."""
        ...

    def enable(self, service_name: str) -> bool:
        ...

    def disable(self, service_name: str) -> bool:
        ...

    def status(self, service_name: str) -> ServiceStatus:
        ...

    def is_active(self, service_name: str) -> bool:
        ...

    def is_enabled(self, service_name: str) -> bool:
        ...

    def is_available(self) -> bool:
        ...
