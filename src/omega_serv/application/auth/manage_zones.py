"""Cas d'usage `omega-serv auth create-zone/remove-zone` (spec §15.3/§15.4)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.core.i18n import _
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
        return ManageZonesResult(False, _("une zone existe déjà pour {path_prefix!r}").format(path_prefix=zone.path_prefix))

    zones_repo.save(existing + (zone,))
    return ManageZonesResult(True, _("Zone {path_prefix!r} créée.").format(path_prefix=zone.path_prefix))


def remove_zone(zones_repo: AuthZonesRepositoryPort, path_prefix: str) -> ManageZonesResult:
    existing = zones_repo.load()
    remaining = tuple(z for z in existing if z.path_prefix != path_prefix)
    if len(remaining) == len(existing):
        return ManageZonesResult(False, _("zone introuvable : {path_prefix!r}").format(path_prefix=path_prefix))

    zones_repo.save(remaining)
    return ManageZonesResult(True, _("Zone {path_prefix!r} retirée.").format(path_prefix=path_prefix))


def update_zone(zones_repo: AuthZonesRepositoryPort, original_prefix: str, zone: AuthZone) -> ManageZonesResult:
    """Modifie une zone en place (demande de l'auteur du 2026-11-15 : une faute de frappe ne doit plus obliger a
    supprimer et tout ressaisir). La zone garde sa position ; un nouveau prefixe ne doit pas deja appartenir a une
    AUTRE zone."""
    error = validate_auth_zone(zone)
    if error is not None:
        return ManageZonesResult(False, error)

    existing = zones_repo.load()
    if not any(z.path_prefix == original_prefix for z in existing):
        return ManageZonesResult(False, _("zone introuvable : {path_prefix!r}").format(path_prefix=original_prefix))
    if zone.path_prefix != original_prefix and any(z.path_prefix == zone.path_prefix for z in existing):
        return ManageZonesResult(False, _("une zone existe déjà pour {path_prefix!r}").format(path_prefix=zone.path_prefix))

    zones_repo.save(tuple(zone if z.path_prefix == original_prefix else z for z in existing))
    return ManageZonesResult(True, _("Zone {path_prefix!r} modifiée.").format(path_prefix=zone.path_prefix))
