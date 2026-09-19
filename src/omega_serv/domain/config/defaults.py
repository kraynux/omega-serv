"""Couche 1 de l'ordre de fusion de configuration (spec §6.4) :
"valeurs sures integrees au programme", avant tout profil, option ou
personnalisation utilisateur. Le moteur de fusion complet (profil +
options + overlay + exceptions de zone + validation finale) est
construit en Phase 3 - ce module expose uniquement cette premiere
couche, deja necessaire pour donner un sens a "une configuration
minimale valide" en Phase 0."""
from __future__ import annotations

from omega_serv.domain.config.entities import OmegaServConfig


def builtin_safe_defaults() -> OmegaServConfig:
    """Les valeurs par defaut des dataclasses de domain/config/entities.py
    SONT ces valeurs sures : bind local, methodes GET/HEAD seules,
    toutes les options desactivees. Cette fonction nomme explicitement
    ce concept plutot que de laisser le lecteur deviner que
    OmegaServConfig() a une signification particuliere."""
    return OmegaServConfig()
