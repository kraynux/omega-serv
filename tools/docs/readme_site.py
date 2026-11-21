"""Pages readme.html du site (17 langues) generees depuis les README - outil de developpement.

Decision de l'auteur du 2026-11-18 (passe 3.0.0) : le contenu de ~/DEV/SERV/html/readme.html et de ses 16
traductions n'est plus recopie a la main ; il est produit ici depuis le README de la langue :

    html/readme.html                      <- omega-serv/README.md
    html/translation/<code>/readme.html   <- omega-serv/docs/translation/<code>/README.md

Usage (depuis la racine du depot omega-serv, python-markdown requis) :
    python3 tools/docs/readme_site.py             # 17 langues
    python3 tools/docs/readme_site.py fr en       # langues choisies

Seul le bloc <div class="content"> ... jusqu'a la NAVIGATION est remplace : en-tete, bandeau, barre des langues,
boutons, pied de page et scripts restent ceux de la page (deja traduits). Comme pour omega-log, la page ne garde
ni logo du README, ni captures, ni badges, ni barre markdown des langues. Le sommaire devient le bloc repliable
habituel (details.readme-toc), les blocs de code recoivent le bouton Copier de la page, les ancres suivent le calcul
de GitHub, si bien que les liens du README marchent tels quels. Verification : chaque lien #ancre existe."""
from __future__ import annotations

import html
import re
import sys
import unicodedata
from pathlib import Path

import markdown

REPO = Path(__file__).resolve().parents[2]
SITE = REPO.parent / "html"
LANGUAGES = ("fr", "en", "es", "pt-BR", "it", "de", "nl", "pl", "ru", "zh-CN", "vi", "th", "id", "ja", "ko", "hi",
             "ar")
LICENSE_URL = "https://opensource.org/license/mit"
CONTENT_START = '    <div class="content">\n'
NAVIGATION = "        <!-- ==================== NAVIGATION ==================== -->"
MARK = "        <!-- GENERE : tools/docs/readme_site.py depuis le README de la langue, ne pas modifier a la main -->"


def readme_path(code: str) -> Path:
    return REPO / "README.md" if code == "fr" else REPO / "docs" / "translation" / code / "README.md"


def page_path(code: str) -> Path:
    return SITE / "readme.html" if code == "fr" else SITE / "translation" / code / "readme.html"


def github_slug(value: str, separator: str = "-") -> str:
    """Ancre calculee comme GitHub : minuscules, lettres/marques/chiffres/_ gardes, espaces -> '-'."""
    value = html.unescape(re.sub(r"<[^>]+>", "", value)).strip().lower()
    kept = "".join(c for c in value if c in " -" or unicodedata.category(c)[0] in "LMN" or unicodedata.category(c) == "Pc")
    return kept.replace(" ", separator)


def strip_readme(text: str) -> str:
    """Retire commentaire, logo, captures, badges et barre des langues (rien de cela dans la page)."""
    text = re.sub(r"<!--.*?-->\s*", "", text, count=1, flags=re.S)
    text = re.sub(r'<div align="center">.*?</div>\s*', "", text, count=1, flags=re.S)
    text = re.sub(r'<p align="center">.*?</p>\s*', "", text, flags=re.S)
    kept: list[str] = []
    for line in text.splitlines():
        if line.startswith(("[![", "![")) or "flagcdn.com" in line:
            continue
        kept.append(line)
    text = "\n".join(kept)
    # ligne « **Langues :** » restee seule avant le separateur
    text = re.sub(r"\n\*\*[^*\n]{1,40}\*\*\s*\n(?=\s*\n---)", "\n", text)
    return text


def widen_lists(text: str) -> str:
    """python-markdown veut 4 espaces par niveau de liste, GitHub en accepte 2 : on double hors des blocs de code."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced:
            match = re.match(r"^( +)([-*] |\d+\. )", line)
            if match:
                line = " " * (2 * len(match.group(1))) + line[len(match.group(1)):]
        out.append(line)
    return "\n".join(out)


def rewrite_links(body: str, code: str) -> str:
    base = "/omega-serv/" if code == "fr" else f"/omega-serv/translation/{code}/"
    body = re.sub(r'href="(?:\.\./)*LICENSE"', f'href="{LICENSE_URL}"', body)
    for name in ("comparatif-serveurs-web", "comparatif-server-web-graphique"):
        body = re.sub(rf'href="(?:docs/)?{name}\.md"', f'href="{base}{name}.html"', body)
    body = re.sub(r'<a href="(?:\.\./)*(?:docs/)?HELP\.md">(.*?)</a>', r"<code>\1</code>", body)
    body = re.sub(r'<a href="[^"]*README\.md">(.*?)</a>', r"\1", body)
    return body


def copy_label(page: str) -> str:
    match = re.search(r'<button class="copy-btn">([^<]*)</button>', page)
    return match.group(1) if match else "Copier"


def body_html(code: str, page: str) -> str:
    source = widen_lists(strip_readme(readme_path(code).read_text(encoding="utf-8")))
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"slugify": github_slug}})
    body = rewrite_links(md.convert(source), code)
    # sommaire : premier titre de niveau 2 suivi d'une liste -> bloc repliable
    body = re.sub(r'<h2 id="([^"]+)">([^<]+)</h2>\s*<ul>(.*?)</ul>\s*(?=<h2)',
                  lambda m: (f'<details class="readme-toc" id="{m.group(1)}">\n<summary><span class="toc-title">📑 '
                             f'{m.group(2)}</span></summary>\n<ul class="toc-list">{m.group(3)}</ul>\n</details>\n'),
                  body, count=1, flags=re.S)
    body = re.sub(r'<p><a href="(#[^"]+)">(↑[^<]*)</a></p>', r'<p class="toc-back"><a href="\1">\2</a></p>', body)
    label = copy_label(page)
    body = re.sub(r"(<pre><code[^>]*>.*?</code></pre>)",
                  rf'<div class="code-block-wrapper">\n\1\n<button class="copy-btn">{label}</button>\n</div>',
                  body, flags=re.S)
    return body


def check_anchors(body: str, code: str) -> list[str]:
    ids = set(re.findall(r'\bid="([^"]+)"', body))
    return sorted({a for a in re.findall(r'href="#([^"]+)"', body) if a not in ids})


def build(code: str) -> str:
    path = page_path(code)
    page = path.read_text(encoding="utf-8")
    start = page.index(CONTENT_START) + len(CONTENT_START)
    end = page.index(NAVIGATION)
    body = body_html(code, page)
    missing = check_anchors(body, code)
    if missing:
        raise SystemExit(f"{code} : ancres introuvables {missing}")
    # pas de retrait ajoute : il se verrait dans les blocs <pre>
    path.write_text(page[:start] + "\n" + MARK + "\n" + body + "\n\n" + page[end:], encoding="utf-8")
    return f"{code} : {len(body)} car., {body.count('<h2')} sections, {body.count('code-block-wrapper')} blocs de code"


def main(argv: list[str]) -> int:
    for code in argv or LANGUAGES:
        if code not in LANGUAGES:
            raise SystemExit(f"langue inconnue : {code}")
        print(build(code))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
