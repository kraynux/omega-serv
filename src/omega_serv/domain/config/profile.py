"""Modele d'un profil de base (spec §6.1/§6.2).

Un profil definit une base coherente (minimal/standard/hardened/
development) que les options et personnalisations completent - jamais
l'inverse. Ce module ne modelise que la structure d'un profil ; le
moteur de fusion profil+options+overlay (spec §9.1, "diff avant
application") est construit en Phase 3, pas ici : la Phase 0 se limite
au chargement et a la validation structurelle d'un profil isole.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KNOWN_PROFILE_NAMES: frozenset[str] = frozenset({
    "minimal",
    "standard",
    "hardened",
    "development",
})


@dataclass(frozen=True)
class Profile:
    """Un profil nomme : les valeurs de configuration qu'il impose,
    sous la meme forme que la configuration finale (mêmes cles que
    OmegaServConfig.to_dict()) - resolues par le moteur de fusion de la
    Phase 3, jamais interpretees ici."""
    name: str
    description: str
    values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        name = data.get("name")
        if not name:
            raise ValueError("Un profil doit avoir un champ 'name'.")
        description = data.get("description", "")
        values = {k: v for k, v in data.items() if k not in ("name", "description")}
        return cls(name=name, description=description, values=values)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, **self.values}
