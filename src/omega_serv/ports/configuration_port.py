"""Contrat de persistance de la configuration.

L'ecriture atomique (spec §5.3 : fichier temporaire, fsync, remplacement
atomique, sauvegarde versionnee) est une responsabilite d'infrastructure
(json_config_repository.py) - ce port n'expose que le contrat, jamais
l'implementation tarfile/json/os.replace reelle."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from omega_serv.domain.config.entities import OmegaServConfig


class ConfigurationPort(Protocol):
    def load(self, path: Path) -> OmegaServConfig:
        """Charge et deserialise la configuration depuis `path`.

        Raises:
            ConfigLoadError: si le fichier est absent, illisible ou
                syntaxiquement invalide (JSON malforme).
        """
        ...

    def save(self, path: Path, config: OmegaServConfig) -> None:
        """Ecrit la configuration de maniere atomique (spec §5.3).
        N'effectue AUCUNE validation metier - le validateur
        (application/config/validate_config.py) doit avoir ete appele
        avant par le code appelant."""
        ...
