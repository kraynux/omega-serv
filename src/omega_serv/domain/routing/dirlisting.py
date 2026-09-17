# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
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
from typing import Any

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES

from omega_serv.domain.config.entities import SecurityConfig
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
    # Meme mise en page que les exports HTML (capabilities_report.html.j2/
    # log_archives_report.html.j2) - container/box/table -, transposee en
    # CSS statique plutot qu'un template jinja2 (interdit ici).
    return (
        "*{box-sizing:border-box}"
        # Retour utilisateur : pied de page toujours colle au bas de la
        # PAGE (pas seulement sous le contenu) - "body" en colonne flex
        # pleine hauteur, le pied de page (margin-top:auto plus bas) se
        # pousse alors tout seul vers le bas, meme quand le dossier liste
        # peu d'entrees.
        f"body{{font-family:ui-monospace,'Cascadia Code','SFMono-Regular',Consolas,monospace;"
        f"line-height:1.6;color:{palette.foreground};background:{palette.background};"
        f"padding:20px;margin:0;display:flex;flex-direction:column;min-height:100vh}}"
        f".omega-listing{{max-width:900px;margin:0 auto;background:{palette.surface};"
        f"padding:30px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.3);width:100%}}"
        f"h1{{font-size:1.4rem;color:{palette.foreground};border-bottom:3px solid {palette.accent};"
        f"padding-bottom:10px;margin:0 0 20px}}"
        f".omega-listing-box{{background:{palette.panel};border:1px solid {palette.accent};"
        f"border-radius:8px;padding:8px 20px 20px;margin-bottom:20px}}"
        "ul{list-style:none;margin:0;padding:0}"
        # Retour utilisateur : le trait separateur entre CHAQUE
        # fichier/dossier ("effet grille") est retire - seul reste celui
        # sous "dossier parent" (classe dediee ".omega-parent", jamais la
        # regle generale "li").
        # Retour utilisateur : espacement vertical entre entrees trop
        # genereux (page trop longue avec beaucoup de fichiers) - reduit.
        "li{padding:.15rem .2rem}"
        f"li.omega-parent{{border-bottom:1px solid {palette.surface};margin-bottom:.2rem;padding-bottom:.6rem}}"
        f"a{{color:{palette.accent};text-decoration:none}}"
        "a:hover{text-decoration:underline}"
        # Retour utilisateur : couleur des fichiers distincte de celle
        # des dossiers (qui gardent la couleur de lien par defaut
        # ci-dessus) - meme couleur que le texte du pied de page.
        f"li.omega-file>a{{color:{palette.secondary}}}"
        f".omega-listing-meta{{color:{palette.secondary};margin:0 0 20px;white-space:pre-wrap}}"
        f".omega-listing-footer-wrap{{max-width:900px;margin:0 auto;width:100%;margin-top:auto;padding-top:20px}}"
        f"hr.omega-listing-footer-rule{{border:none;border-top:1px solid {palette.surface};margin:0 0 10px}}"
        f".omega-listing-footer{{text-align:center;color:{palette.secondary};font-size:.8rem;margin:0}}"
        # Retour utilisateur : les icones emoji (Unicode) ne s'affichent
        # pas partout (police d'emoji absente du systeme - signale sous
        # Chrome/Falkon) - repli en pur CSS (geometrie, jamais de glyphe
        # de police) : universellement fiable, aucune dependance externe.
        "li.omega-dir > a::before,li.omega-file > a::before{content:'';"
        "display:inline-block;width:10px;height:10px;margin-right:8px;vertical-align:middle}"
        f"li.omega-dir > a::before{{background:{palette.accent};border-radius:2px}}"
        f"li.omega-file > a::before{{border:1px solid {palette.secondary};border-radius:2px}}"
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


def render_directory_listing_html(
    url_path: str,
    entries: list[str],
    security: SecurityConfig,
    settings: DirlistingSettings | None = None,
    header_content: str | None = None,
    readme_content: str | None = None,
    directory_names: frozenset[str] = frozenset(),
) -> str:
    settings = settings or DirlistingSettings()

    hidden_names = set()
    if settings.hide_header_file:
        hidden_names.add(settings.header_file)
    if settings.hide_readme_file:
        hidden_names.add(settings.readme_file)

    visible = sorted(
        name for name in entries
        if name not in hidden_names and not is_denied_path((name,), security)
    )

    parent_path = _parent_url_path(url_path)
    parent_item = (
        f'<li class="omega-dir omega-parent"><a href="{html.escape(parent_path)}">.. (dossier parent)</a></li>'
        if parent_path is not None else ""
    )
    items = parent_item + "".join(
        f'<li class="{"omega-dir" if name in directory_names else "omega-file"}">'
        f'<a href="{html.escape(url_path.rstrip("/") + "/" + name)}">'
        f'{html.escape(name)}{"/" if name in directory_names else ""}</a></li>'
        for name in visible
    )
    title = html.escape(url_path)

    show_readme = settings.show_readme and readme_content is not None
    header_html = _rendered_side_content(header_content if settings.show_header else None, settings.encode_header)
    readme_html = _rendered_side_content(readme_content if show_readme else None, settings.encode_readme)

    external_css_link = (
        f'<link rel="stylesheet" href="{html.escape(settings.external_css)}">' if settings.external_css else ""
    )

    # Retour utilisateur : pied de page discret "Propulse par OMEGA-SERV"
    # par defaut - masque des que l'utilisateur habille deja lui-meme le
    # dossier via son propre README.txt (show_readme actif ET fichier
    # reellement present, pas seulement le reglage active a vide) : la
    # mention generique devient alors redondante avec sa personnalisation.
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
        # Retour utilisateur : le titre "Index de ..." (et son trait
        # souligne) apparaissait AU-DESSUS d'un HEADER.txt personnalise -
        # deplace en dessous, meme convention que lighttpd (dir-listing.header
        # rendu tout en haut de page, avant le reste) - jamais masque pour
        # autant : reste une information de navigation utile (savoir dans
        # quel dossier on se trouve), contrairement au pied de page
        # generique qui lui disparait completement face a un README.txt.
        f"{header_html}"
        f"<h1>Index de {title}</h1>"
        f"<div class=\"omega-listing-box\"><ul>{items}</ul></div>"
        f"{readme_html}"
        # Retour utilisateur : le pied de page doit coller au bas de la
        # PAGE, pas seulement suivre un contenu court - sorti du conteneur
        # centre ".omega-listing" (qui n'a que la hauteur de son propre
        # contenu) pour vivre au niveau du "body" (flex column pleine
        # hauteur, voir _base_css), seul endroit ou "margin-top:auto"
        # peut reellement le pousser vers le bas.
        "</div>"
        f"{footer_html}"
        "</body></html>"
    )
