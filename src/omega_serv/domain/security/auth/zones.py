# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Parsing/validation des zones protegees (spec §15.2). Meme patron que
domain/routing/redirect.py::parse_redirect_rules - parsing pur, la
resolution de zone reutilise domain/routing/zone_resolver.py (deja
concu pour ce cas d'usage, voir son docstring)."""
from __future__ import annotations

from typing import Any

from omega_serv.domain.security.auth.entities import AuthZone

SUPPORTED_ZONES_FILE_VERSIONS = frozenset({1})


def parse_auth_zones(raw_list: list[dict[str, Any]]) -> list[AuthZone]:
    return [
        AuthZone(
            path_prefix=item["path_prefix"],
            realm=item.get("realm", "Zone protegee"),
            allowed_users=tuple(item.get("allowed_users", [])),
            allow_methods=tuple(item.get("allow_methods", [])),
        )
        for item in raw_list
    ]


def validate_auth_zone(zone: AuthZone) -> str | None:
    if not zone.path_prefix.startswith("/"):
        return f"path_prefix doit commencer par '/' : {zone.path_prefix!r}"
    if not zone.realm:
        return "realm ne peut pas etre vide"
    if not zone.allowed_users:
        return f"la zone {zone.path_prefix!r} n'a aucun allowed_users - personne ne pourrait jamais y acceder"
    return None
