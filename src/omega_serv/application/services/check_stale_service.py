"""Le service actif tourne-t-il avec un code plus ancien que celui installe ?
(domain/services/stale_service.py). Toujours `False` en cas de doute (service
arrete, PID ou dates indisponibles) : un avertissement a tort serait pire que
pas d'avertissement."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from omega_serv.domain.services.stale_service import runs_older_code
from omega_serv.ports.service_manager_port import ServiceManagerPort


def service_runs_older_code(
    manager: ServiceManagerPort,
    service_name: str,
    process_started_at: Callable[[int], datetime | None],
    code_modified_at: datetime | None,
) -> bool:
    if code_modified_at is None:
        return False
    try:
        pid = manager.main_pid(service_name)
    except Exception:  # noqa: BLE001 - diagnostic auxiliaire, jamais une raison d'echouer
        return False
    if pid is None:
        return False
    started_at = process_started_at(pid)
    return started_at is not None and runs_older_code(started_at, code_modified_at)
