"""Implementation reelle de ServiceManagerPort pour OpenRC - portee
depuis omega-fire (service_manager/openrc.py, audite reutilisable),
commandes `rc-service`/`rc-update` inchangees, via ProcessRunnerPort."""
from __future__ import annotations

from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError, ServiceStatusError
from omega_serv.ports.process_runner_port import ProcessRunnerPort
from omega_serv.ports.service_manager_port import ServiceManagerType

_TIMEOUT_SECONDS = 10.0
"""Meme garde-fou que systemd_service_manager.py::_TIMEOUT_SECONDS - un
appel bloque a `rc-service`/`rc-update` gelerait de la meme facon
l'ecran Etat & Ressources (boucle asyncio Textual unique)."""
_TIMEOUT_RETURNCODE = 124
_NOT_FOUND_RETURNCODE = 127


class OpenRCServiceManager:
    def __init__(self, process_runner: ProcessRunnerPort):
        self._runner = process_runner
        self._rc_service = "rc-service"
        self._rc_update = "rc-update"

    def manager_type(self) -> ServiceManagerType:
        return "openrc"

    def _control(self, service_name: str, operation: str) -> bool:
        result = self._runner.run([self._rc_service, service_name, operation], timeout=_TIMEOUT_SECONDS)
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
        return self._control(service_name, "reload")

    def enable(self, service_name: str) -> bool:
        result = self._runner.run([self._rc_update, "add", service_name], timeout=_TIMEOUT_SECONDS)
        if result.returncode == 0:
            return True
        if "not found" in result.stderr.lower():
            raise ServiceNotFoundError(service_name, "openrc")
        raise ServiceControlError(service_name, "enable", result.stderr.strip() or f"code {result.returncode}", "openrc")

    def disable(self, service_name: str) -> bool:
        result = self._runner.run([self._rc_update, "del", service_name], timeout=_TIMEOUT_SECONDS)
        if result.returncode == 0:
            return True
        if "not found" in result.stderr.lower():
            raise ServiceNotFoundError(service_name, "openrc")
        raise ServiceControlError(service_name, "disable", result.stderr.strip() or f"code {result.returncode}", "openrc")

    def status(self, service_name: str) -> ServiceStatus:
        result = self._runner.run([self._rc_service, service_name, "status"], timeout=_TIMEOUT_SECONDS)
        if result.returncode in (_TIMEOUT_RETURNCODE, _NOT_FOUND_RETURNCODE):
            raise ServiceStatusError(
                service_name,
                f"{result.stderr.strip()} - verifiez `rc-service {service_name} status` manuellement, "
                "ou (re)installez le service depuis l'ecran SERVICE",
                "openrc",
            )
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
        result = self._runner.run([self._rc_service, service_name, "status"], timeout=_TIMEOUT_SECONDS)
        return result.returncode == 0

    def is_enabled(self, service_name: str) -> bool:
        result = self._runner.run([self._rc_update, "show"], timeout=_TIMEOUT_SECONDS)
        return result.returncode == 0 and service_name in result.stdout

    def is_available(self) -> bool:
        result = self._runner.run([self._rc_service, "--version"], timeout=_TIMEOUT_SECONDS)
        return result.returncode == 0
