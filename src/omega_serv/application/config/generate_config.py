"""Cas d'usage : `omega-serv config init`."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.config.defaults import builtin_safe_defaults
from omega_serv.ports.configuration_port import ConfigurationPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass
class GenerateConfigResult:
    success: bool
    message: str


def generate_default_config(
    configuration_port: ConfigurationPort,
    filesystem: FilesystemPort,
    config_path: Path,
    force: bool = False,
) -> GenerateConfigResult:
    if filesystem.exists(config_path) and not force:
        return GenerateConfigResult(False, _("{config_path} existe déjà (utiliser --force pour écraser)").format(config_path=config_path))
    configuration_port.save(config_path, builtin_safe_defaults())
    return GenerateConfigResult(True, _("Configuration par défaut écrite dans {config_path}").format(config_path=config_path))
