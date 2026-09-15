# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Modele d'une option superposable (spec §6.3).

Une option ajoute une capacite fonctionnelle par-dessus un profil de
base (waf, auth, dirlisting, fastcgi, aliases, redirects, rewrites,
cache, trusted_proxy, upload, error_pages, reverse_proxy, active_defense
- CGI brut hors perimetre V1, voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §3
Phase 8). Ce module ne modelise que
la forme commune a toutes les options (nom, activation, reglages bruts)
- le contenu detaille de chaque option (ex. le schema complet de
waf.json) est defini par le module qui possede cette option, quand sa
phase arrive (Phase 5 pour waf, Phase 7 pour auth...), pas ici."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Noms d'options reconnus par le moteur de fusion (spec §5.2 "options").
# CGI volontairement absent : abandonne du perimetre V1, voir la
# decision de la Phase 8.
KNOWN_OPTION_NAMES: frozenset[str] = frozenset({
    "waf",
    "auth",
    "dirlisting",
    "fastcgi",
    "aliases",
    "redirects",
    "rewrites",
    "cache",
    "trusted_proxy",
    "upload",
    "error_pages",
    "access_control",
    "reverse_proxy",
    "active_defense",
})


@dataclass(frozen=True)
class Option:
    """Une option nommee, activee ou non, avec ses reglages propres.

    `settings` reste une structure ouverte ici (le contenu detaille de
    chaque option est modelise et valide par sa propre couche quand sa
    phase est implementee) - ce module ne connait que la forme commune.
    """
    name: str
    enabled: bool = False
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> Option:
        data = dict(data)
        enabled = bool(data.pop("enabled", False))
        return cls(name=name, enabled=enabled, settings=data)

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, **self.settings}
