"""Politique Cache-Control par zone et extension (spec §18).

Ordre de resolution : zone (la plus specifique, via zone_resolver)
d'abord, puis extension de fichier, puis valeur par defaut - jamais de
`public` implicite pour une ressource qui pourrait etre authentifiee ou
sensible (spec : "Ne jamais utiliser 'public' pour une ressource
authentifiee... sauf comprehension tres precise")."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone

DEFAULT_CACHE_CONTROL = "no-cache, must-revalidate"


@dataclass(frozen=True)
class CachePolicy:
    default: str = DEFAULT_CACHE_CONTROL
    zones: tuple[Zone[str], ...] = field(default_factory=tuple)
    extensions: dict[str, str] = field(default_factory=dict)


def parse_cache_policy(settings: dict[str, Any]) -> CachePolicy:
    zones = tuple(
        Zone(path_prefix=item["path_prefix"], data=item["cache_control"])
        for item in settings.get("zones", [])
    )
    return CachePolicy(
        default=settings.get("default", DEFAULT_CACHE_CONTROL),
        zones=zones,
        extensions=dict(settings.get("extensions", {})),
    )


def resolve_cache_control(path: str, filename: str, policy: CachePolicy) -> str:
    zone = resolve_zone(path, list(policy.zones))
    if zone is not None:
        return zone.data

    dot_index = filename.rfind(".")
    if dot_index != -1:
        extension = filename[dot_index:].lower()
        if extension in policy.extensions:
            return policy.extensions[extension]

    return policy.default
