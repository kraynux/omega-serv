"""Contrat d'entretien des logs (plan interface §3.4/§8, "retirer une IP
des logs")."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class LogsMaintenancePort(Protocol):
    def remove_ip(self, ip: str, log_path: Path) -> int:
        """Retire du fichier `log_path` toutes les lignes dont l'IP
        source correspond a `ip` (reecriture en place). Retourne le
        nombre de lignes retirees."""
        ...
