"""Construction des objets textual.theme.Theme a partir de
omega_lib.theme.policies. Seul fichier, avec le reste de
interfaces/tui/, autorise a combiner donnees de theme et API Textual.
Porte verbatim depuis omega-check (plan interface §0/§3.1)."""
from __future__ import annotations

from omega_lib.theme.policies import TUI_THEMES, ThemeDefinition
from textual.theme import Theme as TextualTheme


def build_textual_theme(definition: ThemeDefinition) -> TextualTheme:
    """Traduit une palette de omega_lib.theme.policies en objet
    textual.theme.Theme. Textual distingue `primary` (obligatoire) et
    `accent` (optionnel) ; notre modele n'a que `accent` (couleur
    principale) et `secondary` — mappe `primary <- palette.accent` et
    laisse `accent` non renseigne."""
    palette = definition.palette
    return TextualTheme(
        name=definition.name,
        primary=palette.accent,
        secondary=palette.secondary,
        warning=palette.warning,
        error=palette.error,
        success=palette.success,
        foreground=palette.foreground,
        background=palette.background,
        surface=palette.surface,
        panel=palette.panel,
        dark=definition.dark,
        variables={},
    )


def build_all_textual_themes() -> tuple[TextualTheme, ...]:
    """Construit les 10 themes du catalogue, dans l'ordre de
    omega_lib.theme.policies::TUI_THEMES."""
    return tuple(build_textual_theme(definition) for definition in TUI_THEMES.values())
