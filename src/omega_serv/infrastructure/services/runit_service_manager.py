"""Implementation reelle de ServiceManagerPort pour runit - portee
depuis omega-fire (service_manager/runit.py, audite reutilisable),
commande `sv` inchangee, activation/desactivation par symlink dans
`/var/service` (comportement natif de runit, pas une convention
OMEGA-SERV)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError
from omega_serv.ports.process_runner_port import ProcessRunnerPort
from omega_serv.ports.service_manager_port import ServiceManagerType


class RunitServiceManager:
    def __init__(self, process_runner: ProcessRunnerPort, service_dir: str = "/etc/sv", run_dir: str = "/var/service"):
        self._runner = process_runner
        self._sv = "sv"
        self._service_dir = service_dir
        self._run_dir = run_dir

    def manager_type(self) -> ServiceManagerType:
        return "runit"

    def _service_path(self, service_name: str) -> str:
        return str(Path(self._service_dir) / service_name)

    def _control(self, service_name: str, operation: str) -> bool:
        result = self._runner.run([self._sv, operation, self._service_path(service_name)])
        if result.returncode == 0:
            return True
        stderr_lower = result.stderr.lower()
        if "fail" in stderr_lower or "not found" in stderr_lower:
            raise ServiceNotFoundError(service_name, "runit")
        raise ServiceControlError(service_name, operation, result.stderr.strip() or f"code {result.returncode}", "runit")

    def start(self, service_name: str) -> bool:
        return self._control(service_name, "up")

    def stop(self, service_name: str) -> bool:
        return self._control(service_name, "down")

    def restart(self, service_name: str) -> bool:
        return self._control(service_name, "restart")

    def reload(self, service_name: str) -> bool:
        return self._control(service_name, "reload")

    def enable(self, service_name: str) -> bool:
        service_path = Path(self._service_path(service_name))
        if not service_path.exists():
            raise ServiceNotFoundError(service_name, "runit")
        run_path = Path(self._run_dir) / service_name
        try:
            if not run_path.exists():
                run_path.symlink_to(service_path)
            return True
        except OSError as e:
            raise ServiceControlError(service_name, "enable", str(e), "runit") from e

    def disable(self, service_name: str) -> bool:
        run_path = Path(self._run_dir) / service_name
        try:
            if run_path.exists() or run_path.is_symlink():
                run_path.unlink()
            return True
        except OSError as e:
            raise ServiceControlError(service_name, "disable", str(e), "runit") from e

    def status(self, service_name: str) -> ServiceStatus:
        result = self._runner.run([self._sv, "status", self._service_path(service_name)])
        stderr_lower = result.stderr.lower()
        if "fail" in stderr_lower or "not found" in stderr_lower:
            raise ServiceNotFoundError(service_name, "runit")
        active, state, sub_state = self._parse_status(result.stdout)
        return ServiceStatus(
            service_name=service_name, active=active, enabled=self.is_enabled(service_name),
            state=state, sub_state=sub_state,
        )

    def is_active(self, service_name: str) -> bool:
        result = self._runner.run([self._sv, "status", self._service_path(service_name)])
        return result.returncode == 0 and "run:" in result.stdout

    def is_enabled(self, service_name: str) -> bool:
        run_path = Path(self._run_dir) / service_name
        return run_path.exists() or run_path.is_symlink()

    def is_available(self) -> bool:
        result = self._runner.run([self._sv])
        return result.returncode in (0, 1)

    @staticmethod
    def _parse_status(output: str) -> tuple[bool, str, str]:
        if "run:" in output:
            return True, "run", "running"
        if "down:" in output:
            return False, "down", "stopped"
        if "finish:" in output:
            return False, "finish", "finished"
        return False, "unknown", "unknown"
