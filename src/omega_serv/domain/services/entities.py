"""Entites pures de gestion de service (spec §24). Porte depuis
omega-fire (infrastructure/backends/service_manager/adapter.py::ServiceStatus,
audite reutilisable tel quel, voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §5)
- simplifie en dataclass immuable (convention OMEGA-SERV : Protocol
plutot qu'ABC, dataclass plutot que classe a etat mutable) plutot que
copie telle quelle."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceStatus:
    service_name: str
    active: bool
    enabled: bool
    state: str = "unknown"
    sub_state: str = ""
    description: str = ""

    @property
    def is_running(self) -> bool:
        return self.active and self.sub_state == "running"

    @property
    def is_failed(self) -> bool:
        return self.state == "failed"
