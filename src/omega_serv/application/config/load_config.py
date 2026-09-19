"""Cas d'usage : charger et valider la configuration au demarrage.

Orchestre le port de configuration (I/O reelle deleguee) et le
validateur structurel du domaine (pur) - ne fait jamais d'I/O
directement lui-meme (charte : application/ orchestre via domain/ et
ports/, jamais d'appel direct a subprocess/sockets/fichiers)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.exceptions import ConfigLoadError
from omega_serv.domain.config.validation import validate_config
from omega_serv.ports.configuration_port import ConfigurationPort


@dataclass
class LoadConfigResult:
    success: bool
    config: OmegaServConfig | None = None
    errors: list[str] = field(default_factory=list)


def load_config(configuration_port: ConfigurationPort, path: Path) -> LoadConfigResult:
    try:
        config = configuration_port.load(path)
    except ConfigLoadError as e:
        return LoadConfigResult(success=False, errors=[str(e)])

    errors = validate_config(config)
    if errors:
        return LoadConfigResult(success=False, errors=errors)

    return LoadConfigResult(success=True, config=config)
