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
from typing import Any, cast

from omega_serv.core.i18n import _

KNOWN_PROFILE_NAMES: frozenset[str] = frozenset({
    "minimal",
    "standard",
    "hardened",
    "development",
})


_METADATA = frozenset({"name", "description", "label", "custom", "selection", "created_at"})


@dataclass(frozen=True)
class Profile:
    """Un profil nomme : les valeurs de configuration qu'il impose,
    sous la meme forme que la configuration finale (mêmes cles que
    OmegaServConfig.to_dict()) - resolues par le moteur de fusion de la
    Phase 3, jamais interpretees ici."""
    name: str
    description: str
    values: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    """Profil personnalise (2026-11-15) : libelle affiche (tableau de bord), choix d'origine, date."""
    custom: bool = False
    selection: dict[str, str] = field(default_factory=dict)
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        name = data.get("name")
        if not name:
            raise ValueError(_("Un profil doit avoir un champ 'name'."))
        description = data.get("description", "")
        # Fiche d'un profil personnalise (label, custom, selection, created_at) : jamais des valeurs de configuration.
        values = {k: v for k, v in data.items() if k not in _METADATA}
        selection: dict[Any, Any] = cast("dict[Any, Any]", data.get("selection")) if isinstance(data.get("selection"), dict) else {}
        return cls(name=name, description=description, values=values, label=str(data.get("label", "")),
                   custom=bool(data.get("custom", False)), selection={str(k): str(v) for k, v in selection.items()},
                   created_at=str(data.get("created_at", "")))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "description": self.description}
        if self.custom:
            data.update(label=self.label, custom=True, selection=dict(self.selection), created_at=self.created_at)
        return {**data, **self.values}
