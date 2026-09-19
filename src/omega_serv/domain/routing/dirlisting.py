"""Rendu HTML du directory listing (spec §16).

Regles appliquees : dotfiles et extensions/motifs sensibles masques
(reutilise domain/security/access_policy.py - meme regle qu'un acces
direct au fichier, propriete utile : jamais rien de visible dans un
listing qui serait refuse en acces direct) ; tous les noms de fichiers
sont echappes HTML (spec : "Ne jamais generer de HTML avec des noms de
fichiers non echappes").

Personnalisation (retour utilisateur - guide d'aide, point 1 : CSS de
base + header/readme façon lighttpd `dir-listing.*`) portee par
`DirlistingSettings` : CSS toujours genere en ligne (jamais de jinja2
ici - confine a infrastructure/exporters/html_exporter.py par contrat
import-linter dedie), reutilisant le meme catalogue de themes que le
reste de la suite (`omega_lib.theme.policies.EXPORT_PALETTES`, D-007/
D-008) plutot qu'une palette isolee - defaut "omega-base", exactement
le theme demande. `header_content`/`readme_content` arrivent deja lus
depuis le disque (ce module reste pur, sans I/O - la lecture reelle est
la responsabilite de application/server/serve_static_file.py, seul
detenteur d'un FilesystemPort)."""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.routing.dirlisting_sort import (
    DirEntryInfo,
    DirlistingSort,
    SortKey,
    parse_dirlisting_sort,
    sort_entry_names,
)
from omega_serv.domain.routing.icon_registry import DIRECTORY_ICON, ICON_URL_PREFIX, icon_for_file
from omega_serv.domain.security.access_policy import is_denied_path

DEFAULT_HEADER_FILE = "HEADER.txt"
DEFAULT_README_FILE = "README.txt"


@dataclass(frozen=True)
class DirlistingSettings:
    theme: str = DEFAULT_EXPORT_THEME
    external_css: str = ""
    show_header: bool = False
    header_file: str = DEFAULT_HEADER_FILE
    encode_header: bool = False
    hide_header_file: bool = True
    show_readme: bool = False
    readme_file: str = DEFAULT_README_FILE
    encode_readme: bool = False
    hide_readme_file: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DirlistingSettings:
        defaults = cls()
        return cls(
            theme=data.get("theme", defaults.theme),
            external_css=data.get("external_css", defaults.external_css),
            show_header=bool(data.get("show_header", defaults.show_header)),
            header_file=data.get("header_file", defaults.header_file) or defaults.header_file,
            encode_header=bool(data.get("encode_header", defaults.encode_header)),
            hide_header_file=bool(data.get("hide_header_file", defaults.hide_header_file)),
            show_readme=bool(data.get("show_readme", defaults.show_readme)),
            readme_file=data.get("readme_file", defaults.readme_file) or defaults.readme_file,
            encode_readme=bool(data.get("encode_readme", defaults.encode_readme)),
            hide_readme_file=bool(data.get("hide_readme_file", defaults.hide_readme_file)),
        )


def _base_css(theme: str) -> str:
    palette = EXPORT_PALETTES.get(theme, EXPORT_PALETTES[DEFAULT_EXPORT_THEME])
    return (
        "*{box-sizing:border-box}"
        f"body{{font-family:ui-monospace,'Cascadia Code','SFMono-Regular',Consolas,monospace;"
        f"line-height:1.6;color:{palette.foreground};background:{palette.background};"
        f"padding:20px;margin:0;display:flex;flex-direction:column;min-height:100vh}}"
        f".omega-listing{{max-width:900px;margin:0 auto;background:{palette.surface};"
        f"padding:30px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.3);width:100%}}"
        f".omega-listing-title{{font-size:1.05rem;color:{palette.foreground};"
        f"border-bottom:3px solid {palette.accent};padding-bottom:10px;margin:0 0 20px}}"
        f".omega-listing-box{{background:{palette.panel};border:1px solid {palette.accent};"
        f"border-radius:8px;padding:8px 20px 20px;margin-bottom:20px}}"
        "ul{list-style:none;margin:0;padding:0}"
        "li{padding:.15rem .2rem;display:flex;align-items:center;gap:.5rem}"
        f"li.omega-parent{{border-bottom:1px solid {palette.surface};margin-bottom:.2rem;padding-bottom:.6rem}}"
        f"a{{color:{palette.accent};text-decoration:none}}"
        "a:hover{text-decoration:underline}"
        f"li.omega-file>a{{color:{palette.secondary}}}"
        ".omega-listing-name{flex:1 1 auto;min-width:0;overflow:hidden;"
        "text-overflow:ellipsis;white-space:nowrap}"
        f".omega-listing-mtime{{flex:0 0 190px;text-align:right;"
        f"color:{palette.secondary};font-size:.8rem}}"
        f".omega-listing-size{{flex:0 0 80px;text-align:right;"
        f"color:{palette.secondary};font-size:.8rem}}"
        f".omega-listing-header{{font-size:.75rem}}"
        f".omega-listing-header a{{color:{palette.accent};opacity:.7}}"
        f".omega-listing-meta{{color:{palette.secondary};margin:0 0 20px;white-space:pre-wrap}}"
        f".omega-listing-footer-wrap{{max-width:900px;margin:0 auto;width:100%;margin-top:auto;padding-top:20px}}"
        f"hr.omega-listing-footer-rule{{border:none;border-top:1px solid {palette.surface};margin:0 0 10px}}"
        f".omega-listing-footer{{text-align:center;color:{palette.secondary};font-size:.8rem;margin:0}}"
        ".omega-listing-icon{width:16px;height:16px;margin-right:8px;vertical-align:middle}"
    )


def _parent_url_path(url_path: str) -> str | None:
    """Chemin URL du dossier parent, ou None si `url_path` est deja la
    racine servie (retour utilisateur : "il manque le lien dossier
    parent") - jamais de lien vers un parent inexistant a la racine."""
    trimmed = url_path.rstrip("/")
    if not trimmed:
        return None
    parent = trimmed.rsplit("/", 1)[0]
    return f"{parent}/" if parent else "/"


def _rendered_side_content(raw_content: str | None, encode: bool) -> str:
    if raw_content is None:
        return ""
    if encode:
        return f"<pre class=\"omega-listing-meta\">{html.escape(raw_content)}</pre>"
    return raw_content


def _format_mtime(mtime: float | None) -> str:
    """UTC, jamais l'heure locale du serveur (meme convention que le
    reste du projet - ex. `infrastructure/storage/files/archive_store.py`
    - un timestamp naif serait ambigu pour qui consulte ce listing HTML
    public depuis un fuseau different)."""
    if mtime is None:
        return ""
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


_SIZE_UNITS = ("o", "Ko", "Mo", "Go", "To", "Po")


def _format_size(size: int | None) -> str:
    """`None` (dossier, jamais de taille recursive calculee - voir
    `DirEntryInfo`) rend "-", jamais une valeur numerique trompeuse."""
    if size is None:
        return "-"
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(_SIZE_UNITS) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {_SIZE_UNITS[unit_index]}"
    return f"{value:.1f} {_SIZE_UNITS[unit_index]}"


def _header_link(label: str, key: SortKey, sort: DirlistingSort) -> str:
    return f'<a class="omega-listing-{key}" href="?{sort.query_for(key)}">{label}</a>'


def _render_entry_item(name: str, info: DirEntryInfo, url_path: str) -> str:
    css_class = "omega-dir" if info.is_directory else "omega-file"
    href = html.escape(url_path.rstrip("/") + "/" + name)
    icon = icon_for_file(name, is_directory=info.is_directory)
    label = html.escape(name) + ("/" if info.is_directory else "")
    return (
        f'<li class="{css_class}">'
        f'<a class="omega-listing-name" href="{href}">'
        f'<img class="omega-listing-icon" src="{ICON_URL_PREFIX}{icon}" alt="">{label}</a>'
        f'<span class="omega-listing-mtime">{_format_mtime(info.mtime)}</span>'
        f'<span class="omega-listing-size">{_format_size(info.size)}</span>'
        "</li>"
    )


def render_directory_listing_html(
    url_path: str,
    entries: list[str],
    security: SecurityConfig,
    settings: DirlistingSettings | None = None,
    header_content: str | None = None,
    readme_content: str | None = None,
    entry_info: dict[str, DirEntryInfo] | None = None,
    query: str = "",
) -> str:
    settings = settings or DirlistingSettings()
    entry_info = entry_info or {}

    hidden_names = set()
    if settings.hide_header_file:
        hidden_names.add(settings.header_file)
    if settings.hide_readme_file:
        hidden_names.add(settings.readme_file)

    visible_names = [
        name for name in entries
        if name not in hidden_names and not is_denied_path((name,), security)
    ]
    sort = parse_dirlisting_sort(query)
    visible = sort_entry_names(visible_names, entry_info, sort)

    criteria_item = (
        f'<li class="omega-listing-header">'
        f'{_header_link("NOM", "name", sort)}'
        f'{_header_link("DERNIÈRE MODIFICATION", "mtime", sort)}'
        f'{_header_link("TAILLE", "size", sort)}'
        "</li>"
    )
    parent_path = _parent_url_path(url_path)
    parent_item = (
        f'<li class="omega-dir omega-parent"><a class="omega-listing-name" href="{html.escape(parent_path)}">'
        f'<img class="omega-listing-icon" src="{ICON_URL_PREFIX}{DIRECTORY_ICON}" alt="">'
        ".. (dossier parent)</a>"
        '<span class="omega-listing-mtime"></span><span class="omega-listing-size"></span></li>'
        if parent_path is not None else ""
    )
    items = criteria_item + parent_item + "".join(
        _render_entry_item(name, entry_info.get(name, DirEntryInfo()), url_path) for name in visible
    )
    title = html.escape(url_path)

    show_readme = settings.show_readme and readme_content is not None
    header_html = _rendered_side_content(header_content if settings.show_header else None, settings.encode_header)
    readme_html = _rendered_side_content(readme_content if show_readme else None, settings.encode_readme)

    external_css_link = (
        f'<link rel="stylesheet" href="{html.escape(settings.external_css)}">' if settings.external_css else ""
    )

    footer_html = (
        ""
        if show_readme
        else (
            '<div class="omega-listing-footer-wrap">'
            '<hr class="omega-listing-footer-rule">'
            '<p class="omega-listing-footer">Propuls&eacute; par OMEGA-SERV</p>'
            "</div>"
        )
    )

    return (
        "<!DOCTYPE html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        f"<title>Index de {title}</title>"
        f"<style>{_base_css(settings.theme)}</style>{external_css_link}"
        "</head><body><div class=\"omega-listing\">"
        f"{header_html}"
        f'<h1 class="omega-listing-title">Index de {title}</h1>'
        f"<div class=\"omega-listing-box\"><ul>{items}</ul></div>"
        f"{readme_html}"
        "</div>"
        f"{footer_html}"
        "</body></html>"
    )
