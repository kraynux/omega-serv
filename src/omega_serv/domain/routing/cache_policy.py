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

_ONE_HOUR = "max-age=3600"
_ONE_DAY = "max-age=86400"
_ONE_WEEK = "max-age=604800"
DEFAULT_EXTENSION_CACHE: dict[str, str] = {
    # Images et medias : rarement modifies, souvent nombreux sur une meme page (galerie
    # de captures : ~130 requetes evitees a chaque visite, et donc jamais de 429).
    **dict.fromkeys((".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico"), _ONE_DAY),
    **dict.fromkeys((".mp4", ".webm", ".mp3", ".ogg"), _ONE_DAY),
    **dict.fromkeys((".woff", ".woff2", ".ttf", ".otf"), _ONE_WEEK),
    # Styles et scripts : une mise a jour du site est visible en moins d'une heure.
    **dict.fromkeys((".css", ".js"), _ONE_HOUR),
}
"""Regles par extension appliquees tant que la configuration n'a pas sa propre table
`extensions` (decision utilisateur 2026-10-26, etude performance point 3) : modifiables dans
l'ecran Cache - toute modification y enregistre une table complete, qui remplace celle-ci.
Jamais de `public` (voir docstring du module) ; le reste (HTML...) garde `default`,
revalide a chaque fois mais a moindre cout grace a l'ETag (304)."""


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
        extensions=dict(settings.get("extensions", DEFAULT_EXTENSION_CACHE)),
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
