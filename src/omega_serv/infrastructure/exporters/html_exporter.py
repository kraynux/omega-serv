"""Export HTML (Jinja2 + theme d'export choisi). Seul module autorise a
importer jinja2 directement - voir contrat import-linter "jinja2
seulement dans infrastructure.exporters.html_exporter" dans
pyproject.toml.

Systeme de theme d'export porte depuis omega-check (D-007/D-008,
catalogue dans omega_lib.theme.policies.EXPORT_PALETTES) : independant
du theme d'interface actif au moment de l'export - voir
html_theme_resolver.py. Retour utilisateur (2026-09-09) : les exports
HTML doivent utiliser le meme mecanisme que le reste de la suite plutot
que du HTML brut concatene directement dans interfaces.tui/."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape
from omega_lib.theme.policies import DEFAULT_EXPORT_THEME

if TYPE_CHECKING:
    from omega_serv.core.capability import Capability

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def export_capabilities_html(capabilities: Sequence[Capability], theme_name: str = DEFAULT_EXPORT_THEME) -> str:
    from omega_serv.infrastructure.exporters.html_theme_resolver import resolve_export_palette

    template = _env.get_template("capabilities_report.html.j2")
    palette = resolve_export_palette(theme_name)
    return template.render(
        capabilities=capabilities,
        generated_at=datetime.now(timezone.utc).isoformat(),
        palette=palette,
    )


def export_log_archives_html(archives: Sequence[dict], theme_name: str = DEFAULT_EXPORT_THEME) -> str:
    from omega_serv.infrastructure.exporters.html_theme_resolver import resolve_export_palette

    template = _env.get_template("log_archives_report.html.j2")
    palette = resolve_export_palette(theme_name)
    return template.render(
        archives=archives,
        generated_at=datetime.now(timezone.utc).isoformat(),
        palette=palette,
    )


def export_guide_html(
    screen_guides: Sequence[dict], faq_entries: Sequence[dict], theme_name: str = DEFAULT_EXPORT_THEME,
) -> str:
    """`screen_guides`/`faq_entries` : deja des dicts simples (`dataclasses.
    asdict()` cote appelant, interfaces/tui/screens/guide_menu_screen.py) -
    ce module reste agnostique du modele `ScreenGuide`/`FaqEntry`
    (interfaces.tui), meme raison que `export_log_archives_html` prend
    des dicts plutot qu'un type de infrastructure/storage/."""
    from omega_serv.infrastructure.exporters.html_theme_resolver import resolve_export_palette

    template = _env.get_template("guide_report.html.j2")
    palette = resolve_export_palette(theme_name)
    return template.render(
        screen_guides=screen_guides,
        faq_entries=faq_entries,
        generated_at=datetime.now(timezone.utc).isoformat(),
        palette=palette,
    )
