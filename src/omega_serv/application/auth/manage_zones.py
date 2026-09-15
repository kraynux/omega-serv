# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `omega-serv auth create-zone/remove-zone` (spec §15.3/§15.4)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.security.auth.entities import AuthZone
from omega_serv.domain.security.auth.zones import validate_auth_zone
from omega_serv.ports.auth_zones_repository_port import AuthZonesRepositoryPort


@dataclass(frozen=True)
class ManageZonesResult:
    success: bool
    message: str


def add_zone(zones_repo: AuthZonesRepositoryPort, zone: AuthZone) -> ManageZonesResult:
    error = validate_auth_zone(zone)
    if error is not None:
        return ManageZonesResult(False, error)

    existing = zones_repo.load()
    if any(z.path_prefix == zone.path_prefix for z in existing):
        return ManageZonesResult(False, f"une zone existe deja pour {zone.path_prefix!r}")

    zones_repo.save(existing + (zone,))
    return ManageZonesResult(True, f"Zone {zone.path_prefix!r} creee.")


def remove_zone(zones_repo: AuthZonesRepositoryPort, path_prefix: str) -> ManageZonesResult:
    existing = zones_repo.load()
    remaining = tuple(z for z in existing if z.path_prefix != path_prefix)
    if len(remaining) == len(existing):
        return ManageZonesResult(False, f"zone introuvable : {path_prefix!r}")

    zones_repo.save(remaining)
    return ManageZonesResult(True, f"Zone {path_prefix!r} retiree.")
