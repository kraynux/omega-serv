"""Partie 2 du guide du site (« Guide d'aide integre ») generee depuis l'aide F1 de la TUI - outil de developpement.

Decision de l'auteur du 2026-11-18 : la Partie 2 de ~/DEV/SERV/html/guide.html (et de ses 16 traductions) n'est plus
recopiee a la main ; elle est produite ici a partir des fiches (interfaces/tui/guide/) et de la FAQ integree, dans
chaque langue par les catalogues .po. Elle reste donc toujours identique a F1. La Partie 1 (presentation, concepts,
scenarios, exploitation, depannage) et les Annexes restent ecrites a la main.

Usage (depuis la racine du depot omega-serv) :
    .venv/bin/python tools/docs/guide_site.py            # 17 langues
    .venv/bin/python tools/docs/guide_site.py fr en      # langues choisies

Remplace, dans chaque page, tout ce qui se trouve entre les marqueurs GENERE-PARTIE-2 (poses au premier passage a la
place des sections « Demarrage rapide » ... « FAQ » ecrites a la main, juste avant « Annexes »). Le titre et
l'introduction de la FAQ, et le mot « fiches », sont repris de la page elle-meme (deja traduits)."""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SITE = REPO.parent / "html"
LANGUAGES = ("fr", "ar", "de", "en", "es", "hi", "id", "it", "ja", "ko", "nl", "pl", "pt_BR", "ru", "th", "vi",
             "zh_CN")
START = "<!-- GENERE-PARTIE-2 : debut (tools/docs/guide_site.py, ne pas modifier a la main) -->"
END = "<!-- GENERE-PARTIE-2 : fin -->"
SEPARATOR = "        <!-- ============================================ -->"
ICONS = ("🏠", "🧭", "🔎", "🎛️", "⚙️", "🔒", "📜", "🖥️", "🧾", "🛡️", "🎨", "📘")
"""Une icone par section du menu Guide, dans l'ordre de menu_tree.py (une section ajoutee prend 📄)."""

_CHILD = r"""
import json, sys
from dataclasses import asdict
from omega_serv.bootstrap.early_language import install_language_early
install_language_early({"OMEGA_SERV_LANG": sys.argv[1], "OMEGA_SERV_EXPORT_CHILD": "1"})
from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.menu_tree import GUIDE_MENU_ENTRIES
from omega_serv.interfaces.tui.guide.registry import ALL_FAQ_ENTRIES, SCREEN_GUIDES
sections = []
for entry in GUIDE_MENU_ENTRIES:
    guide = SCREEN_GUIDES.get(entry.screen_class_name)
    if guide is None:
        continue
    if not sections or sections[-1]["title"] != entry.section:
        sections.append({"title": entry.section, "screens": []})
    sections[-1]["screens"].append(asdict(guide) | {"menu_title": entry.title})
labels = {
    "acces": _("Parcours : {acces}"), "definition": _("Définition : {definition}"),
    "utilisation": _("Utilisation : {utilisation}"), "action": _("Action : {action}"),
    "reaction": _("Réaction : {reaction}"), "consequences": _("CONSÉQUENCES"),
    "vigilance": _("POINTS DE VIGILANCE"),
}
json.dump({"sections": sections, "faq": [asdict(f) for f in ALL_FAQ_ENTRIES], "labels": labels}, sys.stdout,
          ensure_ascii=False)
"""


def page_for(language: str) -> Path:
    return SITE / "guide.html" if language == "fr" else SITE / "translation" / language.replace("_", "-") / "guide.html"


def load_content(language: str) -> dict:
    result = subprocess.run([sys.executable, "-c", _CHILD, language], cwd=REPO, capture_output=True, text=True,
                            env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"}, timeout=120, check=True)
    return json.loads(result.stdout)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def text_html(text: str) -> str:
    """Texte de la TUI -> HTML : echappe, `code` -> <code>, retours a la ligne gardes."""
    escaped = esc(text)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)
    return escaped.replace("\n", "<br>\n")


def label(template: str) -> str:
    """« Définition : {definition} » -> « Définition : » (deja traduit par le catalogue)."""
    return template.split("{", 1)[0].rstrip()


def title_case(text: str) -> str:
    """« CONSÉQUENCES » -> « Conséquences » (sans effet pour les ecritures sans casse)."""
    return text[:1] + text[1:].lower() if text.isupper() else text


def sort_key(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()


def count_text(language: str, count: int) -> str:
    """« 12 fiches » dans la langue de la page, avec ses formes du pluriel (russe, polonais, arabe...)."""
    words = _COUNT_WORDS.get(language)
    if words is None:
        return str(count)
    if language in ("ru", "pl"):
        last, tens = count % 10, count % 100
        if language == "ru" and last == 1 and tens != 11:
            return f"{count} {words[0]}"
        if language == "pl" and count == 1:
            return f"{count} {words[0]}"
        if 2 <= last <= 4 and not 12 <= tens <= 14:
            return f"{count} {words[1]}"
        return f"{count} {words[2]}"
    if language == "ar":
        if count == 1:
            return "بطاقة واحدة"
        if count == 2:
            return "بطاقتان"
        return f"{count} {words[1] if 3 <= count % 100 <= 10 else words[0]}"
    if language == "ko":
        return f"{count}{words[0]}"
    one, many = words[0], words[-1]
    return f"{count} {one if count <= 1 and language in ('fr', 'pt_BR') or count == 1 else many}"


_COUNT_WORDS: dict[str, tuple[str, ...]] = {
    "fr": ("fiche", "fiches"), "en": ("sheet", "sheets"), "de": ("Seite", "Seiten"), "es": ("ficha", "fichas"),
    "pt_BR": ("ficha", "fichas"), "it": ("scheda", "schede"), "nl": ("pagina", "pagina's"),
    "pl": ("karta", "karty", "kart"), "ru": ("карточка", "карточки", "карточек"), "ar": ("بطاقة", "بطاقات"),
    "hi": ("कार्ड",), "id": ("lembar",), "ja": ("件",), "ko": ("개 항목",), "th": ("เอกสาร",), "vi": ("phiếu",),
    "zh_CN": ("张卡片",),
}
"""Mot « fiche » tel que les pages traduites l'emploient deja (2.6)."""


def faq_header(page: str) -> tuple[str, str]:
    """Titre et introduction de la FAQ, repris de la page (deja traduits)."""
    found = re.search(r'<span class="wiki-icon">❓</span>\s*<span class="wiki-title">(.*?)</span>\s*'
                      r'<span class="wiki-count">(.*?)</span>\s*</summary>\s*<div class="wiki-body">\s*<p>(.*?)</p>',
                      page, re.DOTALL)
    if found is None:
        raise SystemExit("section FAQ introuvable : marqueurs deja poses ? relire la page")
    return found.group(1), found.group(3)


def render(content: dict, faq_title: str, faq_intro: str, language: str) -> str:
    labels = content["labels"]
    out: list[str] = [START]
    for index, section in enumerate(content["sections"]):
        icon = ICONS[index] if index < len(ICONS) else "📄"
        out += [SEPARATOR, f"        <!-- SECTION : {section['title'].upper()} -->", SEPARATOR,
                f'        <details class="wiki-section"{" open" if index == 0 else ""}>',
                "            <summary>", f'                <span class="wiki-icon">{icon}</span>',
                f'                <span class="wiki-title">{esc(section["title"])}</span>',
                f'                <span class="wiki-count">{count_text(language, len(section["screens"]))}</span>',
                "            </summary>", '            <div class="wiki-body">']
        for screen in section["screens"]:
            out += render_screen(screen, labels, section["title"])
        out += ["            </div>", "        </details>", ""]
    out += render_faq(content["faq"], faq_title, faq_intro, language)
    out.append(END)
    return "\n".join(out) + "\n"


def render_screen(screen: dict, labels: dict, section: str) -> list[str]:
    out = ["", '                <details class="screen-card">', "                    <summary>",
           f'                        <span class="screen-name">{esc(screen["title"])}</span>',
           f'                        <span class="screen-path">{esc(section)} →</span>',
           "                    </summary>", '                    <div class="screen-body">',
           f"                        <p>{text_html(screen['definition'])}</p>",
           (f'                        <p><span class="label">{esc(label(labels["acces"]))}</span> '
            f"{text_html(screen['acces'])}</p>")]
    for field in screen["fields"]:
        out += ["", '                        <div class="field-card">',
                f'                            <div class="field-name">{esc(field["label"])}</div>']
        for key in ("definition", "utilisation", "action", "reaction"):
            if field[key].strip():
                out.append(f'                            <div class="field-line"><span class="label">'
                           f'{esc(label(labels[key]))}</span> {text_html(field[key])}</div>')
        out.append("                        </div>")
    if screen["consequences"].strip():
        out += ["", '                        <div class="info-box">',
                (f'                            <span class="box-title">ℹ️ {esc(title_case(labels["consequences"]))}'
                 "</span>"), f"                            <p>{text_html(screen['consequences'])}</p>",
                "                        </div>"]
    if screen["points_de_vigilance"]:
        out += ["", '                        <div class="warn-box">',
                (f'                            <span class="box-title">⚠️ {esc(title_case(labels["vigilance"]))}'
                 "</span>"), "                            <ul>"]
        out += [f"                                <li>{text_html(point)}</li>" for point in screen["points_de_vigilance"]]
        out += ["                            </ul>", "                        </div>"]
    out += ["                    </div>", "                </details>"]
    return out


def render_faq(entries: list[dict], title: str, intro: str, language: str) -> list[str]:
    """Meme ordre que l'ecran FAQ de la TUI : themes sans casse ni accents, questions dans l'ordre du fichier."""
    ordered = sorted(entries, key=lambda e: (sort_key(e["category"]), e["category"]))
    out = [SEPARATOR, "        <!-- SECTION : FAQ -->", SEPARATOR, '        <details class="wiki-section">',
           "            <summary>", '                <span class="wiki-icon">❓</span>',
           f'                <span class="wiki-title">{title}</span>',
           f'                <span class="wiki-count">{count_text(language, len(entries))}</span>',
           "            </summary>", '            <div class="wiki-body">', f"                <p>{intro}</p>"]
    for entry in ordered:
        out += ["", '                <details class="faq-item">', "                    <summary>",
                f'                        <span class="faq-question">{esc(entry["question"])}</span>',
                f'                        <span class="faq-cat">{esc(entry["category"])}</span>',
                "                    </summary>", '                    <div class="faq-answer">',
                f"                        {text_html(entry['answer'])}", "                    </div>",
                "                </details>"]
    out += ["            </div>", "        </details>", ""]
    return out


def generated_span(page: str) -> tuple[int, int]:
    """Debut et fin de la zone a remplacer : marqueurs deja poses, sinon les sections ecrites a la main (du
    separateur avant « SECTION : DÉMARRAGE RAPIDE » jusqu'au separateur avant « SECTION : ANNEXES »)."""
    if START in page:
        return page.index(START), page.index(END) + len(END) + 1
    first = page.index("<!-- SECTION : DÉMARRAGE RAPIDE -->")
    annexes = page.index("<!-- SECTION : ANNEXES -->")
    return page.rindex(SEPARATOR, 0, first), page.rindex(SEPARATOR, 0, annexes)


def main(languages: list[str]) -> None:
    for language in languages:
        path = page_for(language)
        page = path.read_text(encoding="utf-8")
        begin, end = generated_span(page)
        title, intro = faq_header(page)
        content = load_content(language)
        block = render(content, title, intro, language)
        path.write_text(page[:begin] + block + page[end:], encoding="utf-8")
        screens = sum(len(s["screens"]) for s in content["sections"])
        print(f"{language:6} {screens} fiches, {len(content['faq'])} questions -> {path.relative_to(SITE)}")


if __name__ == "__main__":
    main(sys.argv[1:] or list(LANGUAGES))
