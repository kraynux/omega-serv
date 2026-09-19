"""Exceptions du module de gestion de service (spec §24). Porte depuis
omega-fire (service_manager/exceptions.py, audite reutilisable), reduit
au sous-ensemble reellement utilise ici - pas de NoServiceManagerDetectedError
ni UnsupportedServiceManagerError separes, un detecteur qui ne trouve
rien retourne simplement "none" (voir infrastructure/services/detector.py)."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class ServiceManagerError(OmegaServError):
    """Racine des erreurs de gestion de service."""


class ServiceNotFoundError(ServiceManagerError):
    def __init__(self, service_name: str, manager_type: str = ""):
        self.service_name = service_name
        self.manager_type = manager_type
        super().__init__(f"service {service_name!r} introuvable ({manager_type})")


class ServiceControlError(ServiceManagerError):
    def __init__(self, service_name: str, operation: str, reason: str, manager_type: str = ""):
        self.service_name = service_name
        self.operation = operation
        self.reason = reason
        self.manager_type = manager_type
        super().__init__(f"echec de {operation} sur {service_name!r} ({manager_type}) : {reason}")


class ServiceStatusError(ServiceManagerError):
    def __init__(self, service_name: str, reason: str, manager_type: str = ""):
        self.service_name = service_name
        self.reason = reason
        self.manager_type = manager_type
        super().__init__(f"echec de lecture du statut de {service_name!r} ({manager_type}) : {reason}")
