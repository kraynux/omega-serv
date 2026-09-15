# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Resolution d'un nom de theme d'export vers sa palette. Aucun import
Jinja2 ici. Porte depuis omega-check (D-007/D-008) : catalogue partage
dans omega_lib.theme.policies."""
from __future__ import annotations

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES, Palette


def resolve_export_palette(theme_name: str) -> Palette:
    """Lookup pur dans le catalogue de omega_lib.theme.policies. Un nom
    inconnu se replie silencieusement sur DEFAULT_EXPORT_THEME."""
    return EXPORT_PALETTES.get(theme_name, EXPORT_PALETTES[DEFAULT_EXPORT_THEME])
