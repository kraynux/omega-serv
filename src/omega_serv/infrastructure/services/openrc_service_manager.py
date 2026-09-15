# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation reelle de ServiceManagerPort pour OpenRC - portee
depuis omega-fire (service_manager/openrc.py, audite reutilisable),
commandes `rc-service`/`rc-update` inchangees, via ProcessRunnerPort."""
from __future__ import annotations

from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError
from omega_serv.ports.process_runner_port import ProcessRunnerPort
from omega_serv.ports.service_manager_port import ServiceManagerType


class OpenRCServiceManager:
    def __init__(self, process_runner: ProcessRunnerPort):
        self._runner = process_runner
        self._rc_service = "rc-service"
        self._rc_update = "rc-update"

    def manager_type(self) -> ServiceManagerType:
        return "openrc"

    def _control(self, service_name: str, operation: str) -> bool:
        result = self._runner.run([self._rc_service, service_name, operation])
        if result.returncode == 0:
            return True
        if "not found" in result.stderr.lower():
            raise ServiceNotFoundError(service_name, "openrc")
        raise ServiceControlError(service_name, operation, result.stderr.strip() or f"code {result.returncode}", "openrc")

    def start(self, service_name: str) -> bool:
        return self._control(service_name, "start")

    def stop(self, service_name: str) -> bool:
        return self._control(service_name, "stop")

    def restart(self, service_name: str) -> bool:
        return self._control(service_name, "restart")

    def reload(self, service_name: str) -> bool:
        # `rc-service <nom> reload` (retour utilisateur 2026-09-11) -
        # meme verbe que start/stop/restart, echoue proprement (meme
        # ServiceControlError que les autres) si le script rc ne
        # l'implemente pas.
        return self._control(service_name, "reload")

    def enable(self, service_name: str) -> bool:
        result = self._runner.run([self._rc_update, "add", service_name])
        if result.returncode == 0:
            return True
        if "not found" in result.stderr.lower():
            raise ServiceNotFoundError(service_name, "openrc")
        raise ServiceControlError(service_name, "enable", result.stderr.strip() or f"code {result.returncode}", "openrc")

    def disable(self, service_name: str) -> bool:
        result = self._runner.run([self._rc_update, "del", service_name])
        if result.returncode == 0:
            return True
        if "not found" in result.stderr.lower():
            raise ServiceNotFoundError(service_name, "openrc")
        raise ServiceControlError(service_name, "disable", result.stderr.strip() or f"code {result.returncode}", "openrc")

    def status(self, service_name: str) -> ServiceStatus:
        result = self._runner.run([self._rc_service, service_name, "status"])
        if "not found" in result.stderr.lower():
            raise ServiceNotFoundError(service_name, "openrc")
        active = result.returncode == 0
        return ServiceStatus(
            service_name=service_name,
            active=active,
            enabled=self.is_enabled(service_name),
            state="started" if active else "stopped",
            sub_state="running" if active else "stopped",
        )

    def is_active(self, service_name: str) -> bool:
        result = self._runner.run([self._rc_service, service_name, "status"])
        return result.returncode == 0

    def is_enabled(self, service_name: str) -> bool:
        result = self._runner.run([self._rc_update, "show"])
        return result.returncode == 0 and service_name in result.stdout

    def is_available(self) -> bool:
        result = self._runner.run([self._rc_service, "--version"])
        return result.returncode == 0
