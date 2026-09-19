"""Cas d'usage : enregistrer une instance dans le registre global
(OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §3/§5 etape 6) - point
d'entree unique qui valide (nom/imbrication/port, domain/instances/
registry.py) AVANT d'ecrire, jamais un ecran qui ecrirait directement."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.instances.registry import validate_new_instance
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.instance_registry_port import InstanceRegistryPort


def register_instance(
    registry: InstanceRegistryPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    *,
    name: str,
    path: Path,
    bind: str,
    port: int,
    service_name: str,
) -> str | None:
    """Retourne un message d'erreur (str) si la validation echoue,
    None si l'instance a ete enregistree avec succes."""
    resolved_path = filesystem.resolve_real_path(path)
    entries = registry.load()
    error = validate_new_instance(entries, name=name, path=resolved_path, bind=bind, port=port)
    if error is not None:
        return error
    entries.append(InstanceEntry(
        name=name, path=resolved_path, bind=bind, port=port,
        service_name=service_name, created_at=clock.now(),
    ))
    registry.save(entries)
    return None
