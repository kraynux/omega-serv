"""Fusion de configuration (spec §6.4, "Ordre de fusion").

Ordre applique ici (les etapes 5-6, exceptions de zone et resolution
de conflits, arrivent avec le concept de zone/ZoneResolver, pas encore
construit) :

    1. Valeurs sures integrees au programme (domain/config/defaults.py)
    2. Profil selectionne (Profile.values, fusion profonde)
    3. Options actuellement actives a conserver (re-appliquees APRES le
       profil : les personnalisations d'une option survivent a un
       changement de profil, spec §9.2 "Options conservees")
    4. Overlay utilisateur explicite

Fonctions pures : ne valide rien (domain/config/validation.py et
domain/config/rules.py s'en chargent separement), ne lit ni n'ecrit
aucun fichier."""
from __future__ import annotations

from typing import Any

from omega_serv.domain.config.defaults import builtin_safe_defaults
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.config.profile import Profile


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Fusionne `overlay` sur `base`, recursivement pour les dictionnaires
    imbriques - une cle non-dict dans l'overlay remplace simplement la
    valeur de base, jamais de fusion de listes (une liste dans l'overlay
    remplace entierement la liste de base, ne la complete pas)."""
    result = dict(base)
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = value
    return result


def compute_merged_config(
    profile: Profile,
    options_to_keep: dict[str, Option],
    user_overlay: dict[str, Any] | None = None,
) -> OmegaServConfig:
    """Calcule la configuration resultante de l'application d'un profil,
    en conservant les options deja actives (spec §9.1/§9.2) et en
    appliquant un overlay utilisateur explicite par-dessus."""
    merged = deep_merge(builtin_safe_defaults().to_dict(), {"profile": profile.name, **profile.values})

    if options_to_keep:
        options_section = dict(merged.get("options", {}))
        for name, option in options_to_keep.items():
            options_section[name] = option.to_dict()
        merged["options"] = options_section

    if user_overlay:
        merged = deep_merge(merged, user_overlay)

    return OmegaServConfig.from_dict(merged)
