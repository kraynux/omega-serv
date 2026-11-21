# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regenere le contenu d'une page HTML du comparatif depuis son markdown - outil de developpement (lot 11).

  python3 tools/docs/comparatif_html.py MARKDOWN PAGE_HTML [--cards FICHIER]

La page existante garde son en-tete, sa barre de langues, ses cartes de chiffres (section 1), sa navigation et son
pied ; seuls le sous-titre, le sommaire, le texte des sections et la phrase du pied sont recrees depuis le markdown,
avec le balisage des pages faites a la main (tableaux : `num` pour un nombre, `ok` / `bad` pour ✅ / ❌, ligne
`highlight` quand la premiere cellule est en gras ; legende en `div.legend`). --cards remplace les cartes."""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SEPARATOR = "    <!-- ============================================================ -->"


def inline(text: str) -> str:
    out, pos = [], 0
    for match in re.finditer(r"`([^`]+)`", text):
        out.append(_inline_plain(text[pos:match.start()]))
        out.append("<code>" + html.escape(match.group(1), quote=False) + "</code>")
        pos = match.end()
    out.append(_inline_plain(text[pos:]))
    return "".join(out)


def _inline_plain(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)\*(?!\w)", r"<em>\1</em>", text)
    text = text.replace("\\*", "*")
    return text


def links(text: str) -> str:
    # [libelle](url) : le libelle peut contenir du code
    def repl(match: re.Match) -> str:
        if not match.group(2).startswith(("http://", "https://", "/")):
            return inline(match.group(1))  # lien relatif du depot (docs/benchmarks/) : pas de page sur le site
        return f'<a href="{match.group(2)}">' + inline(match.group(1)) + "</a>"
    parts, pos = [], 0
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        parts.append(inline(text[pos:match.start()]))
        parts.append(repl(match))
        pos = match.end()
    parts.append(inline(text[pos:]))
    return "".join(parts)


def is_number(cell: str) -> bool:
    plain = re.sub(r"[*`]", "", cell).strip()
    return bool(plain) and (plain[0].isdigit() or plain[0] in "×≈~—−-" and len(plain) > 1 and plain[1].isdigit())


PRE_OPEN = "<pre>"  # traductions : <pre dir='ltr'> (commandes de gauche a droite, meme en arabe)
CELL_CLASSES: dict[str, str] = {}  # contenu d'une cellule -> classe (dim, warn) relevee dans la page existante


def table(lines: list[str]) -> str:
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines]
    header, align, body = rows[0], rows[1], rows[2:]
    right = [a.endswith(":") for a in align]
    th = "".join(f'<th class="num">{links(h)}</th>' if right[i] else f"<th>{links(h)}</th>" for i, h in enumerate(header))
    out = ['    <div class="table-wrap">', "      <table>", f"        <thead><tr>{th}</tr></thead>", "        <tbody>"]
    for row in body:
        cells = []
        for i, cell in enumerate(row):
            css = ""
            if i > 0:
                if cell.startswith("✅"):
                    css = ' class="ok"'
                elif cell.startswith("❌"):
                    css = ' class="bad"'
                elif cell.startswith("⚠️"):
                    css = ' class="warn"'
                elif links(cell) in CELL_CLASSES:
                    css = f' class="{CELL_CLASSES[links(cell)]}"'
                elif is_number(cell):
                    css = ' class="num"'
            cells.append(f"<td{css}>{links(cell)}</td>")
        cls = ' class="highlight"' if row[0].startswith("**") else ""
        out.append(f"          <tr{cls}>{''.join(cells)}</tr>")
    out += ["        </tbody>", "      </table>", "    </div>"]
    return "\n".join(out)


def bullet_list(lines: list[str], ordered: bool = False) -> str:
    items: list[tuple[int, str]] = []
    for line in lines:
        match = re.match(r"^(\s*)(?:[-*]|\d+\.)\s+(.*)$", line)
        if match:
            items.append((len(match.group(1)) // 2, match.group(2)))
        elif items and line.startswith("  "):  # paragraphe en retrait : element a part, au niveau de son retrait
            items.append(((len(line) - len(line.lstrip())) // 2, line.strip()))
        elif items:  # suite d'un element sur la ligne suivante
            depth, text = items[-1]
            items[-1] = (depth, text + " " + line.strip())
    tag = "ol" if ordered else "ul"

    def render(start: int, depth: int) -> tuple[str, int]:
        parts, i = [f"<{tag if depth == 0 else 'ul'}>"], start
        while i < len(items) and items[i][0] >= depth:
            d, text = items[i]
            if d > depth:
                sub, i = render(i, d)
                parts[-1] = parts[-1][: -len("</li>")] + sub + "</li>"
                continue
            parts.append(f"<li>{links(text)}</li>")
            i += 1
        parts.append(f"</{tag if depth == 0 else 'ul'}>")
        return "".join(parts), i

    rendered, _ = render(0, 0)
    return "    " + rendered


LEGEND = ("✅", "🧩", "🔌", "⚙️", "❌")


def legend(lines: list[str]) -> str:
    out = ['    <div class="legend">']
    for line in lines:
        text = re.sub(r"^\s*-\s+", "", line).rstrip(" ;.")
        symbol, _, rest = text.partition(" ")
        css = ' class="ok"' if symbol == "✅" else ' class="bad"' if symbol == "❌" else ""
        out.append(f"      <span><b{css}>{symbol}</b> {links(rest)}</span>")
    out.append("    </div>")
    return "\n".join(out)


def convert(markdown: str) -> dict:
    lines = markdown.splitlines()
    title = next(l[2:] for l in lines if l.startswith("# "))
    subtitle = next(l.strip("*") for l in lines if l.startswith("**") and l.endswith("**"))
    footer = next(l for l in reversed(lines) if l.startswith("*") and l.endswith("*") and not l.startswith("**"))
    first_rule = lines.index("---")
    intro = [l for l in lines[lines.index(next(l for l in lines if l.startswith("**") and l.endswith("**"))) + 1:first_rule]
             if l.strip() and not l.startswith("🌐")]
    sections = []
    current = None
    for line in lines[first_rule:]:
        match = re.match(r"^## (\d+)\. (.*)$", line)
        if match:
            current = {"n": match.group(1), "title": match.group(2), "lines": []}
            sections.append(current)
        elif current is not None and line != footer:
            current["lines"].append(line)
    return {"title": title, "subtitle": subtitle, "footer": footer[1:-1], "intro": intro, "sections": sections}


def blocks(lines: list[str]) -> str:
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip() == "---":
            i += 1
            continue
        if line.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            code = "\n".join(lines[i + 1:j])
            out.append(f"    {PRE_OPEN}<code>" + html.escape(code, quote=False) + "</code></pre>")
            i = j + 1
            continue
        if line.startswith("### "):
            out.append(f"    <h3>{links(line[4:])}</h3>")
            i += 1
            continue
        if line.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append(table(lines[i:j]))
            i = j
            continue
        if re.match(r"^(\s*)(-|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\d+\.", line))
            j = i
            while j < len(lines) and lines[j].strip() and (re.match(r"^\s*(-|\d+\.)\s+", lines[j]) or lines[j].startswith(" ")):
                j += 1
            group = lines[i:j]
            first = re.sub(r"^\s*-\s+", "", group[0])
            if not ordered and all(re.sub(r"^\s*-\s+", "", g).startswith(LEGEND) for g in group):
                if out and out[-1].startswith("    <p>") and out[-1].rstrip().endswith(("：</p>", ":</p>", "：</p>")):
                    out.pop()  # « Legende : » devient le cadre de la legende
                out.append(legend(group))
            else:
                out.append(bullet_list(group, ordered))
            i = j
            continue
        if line.startswith("**") and line.rstrip().endswith("**") and line.count("**") == 2:
            out.append(f"    <p>{links(line)}</p>")
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].strip() and not lines[j].startswith(("|", "#", "```", "- ")) and not re.match(r"^\d+\.\s", lines[j]):
            j += 1
        out.append("    <p>" + links(" ".join(l.strip() for l in lines[i:j])) + "</p>")
        i = j
    return "\n".join(out)


def build(markdown_path: Path, page_path: Path, cards_path: Path | None) -> None:
    page = page_path.read_text(encoding="utf-8")
    global PRE_OPEN
    found = re.search(r"<pre[^>]*>", page)
    if found:
        PRE_OPEN = found.group(0)
    for match in re.finditer(r'<td class="(dim|warn)">(.*?)</td>', page):
        CELL_CLASSES[match.group(2)] = match.group(1)
    doc = convert(markdown_path.read_text(encoding="utf-8"))
    cards = re.search(r"\n    <div class=\"cards\">.*?\n    </div>\n", page, re.S)
    cards_html = cards_path.read_text(encoding="utf-8") if cards_path else (cards.group(0)[1:] if cards else "")
    toc_title = re.search(r'<nav class="toc">\s*<h2>(.*?)</h2>', page).group(1)
    sections = [s for s in doc["sections"]]
    toc = "\n".join(f'        <li><a href="#s{s["n"]}">{links(s["title"])}</a></li>' for s in sections)
    body = [f'    <nav class="toc">\n      <h2>{toc_title}</h2>\n      <ol>\n{toc}\n      </ol>\n    </nav>\n']
    body.append(blocks(doc["intro"]))
    for s in sections:
        body.append(SEPARATOR)
        body.append(f'    <h2 id="s{s["n"]}">{s["n"]}. {links(s["title"])}</h2>')
        if s["n"] == "1" and cards_html:
            body.append(cards_html.rstrip("\n"))
        body.append(blocks(s["lines"]))
    main = "<main>\n\n" + "\n".join(body) + "\n\n  </main>"
    page = re.sub(r"<main>.*?</main>", lambda _: main, page, flags=re.S)
    page = re.sub(r"(<div class=\"title-tag\">.*?<p>)(.*?)(</p>)", lambda m: m.group(1) + inline(doc["subtitle"]) + m.group(3), page, count=1, flags=re.S)
    page = re.sub(r"(<footer class=\"custom-footer\">\s*<p><em>)(.*?)(</em></p>)", lambda m: m.group(1) + links(doc["footer"]) + m.group(3), page, count=1, flags=re.S)
    page_path.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[1:]
    cards = None
    if "--cards" in args:
        k = args.index("--cards")
        cards = Path(args[k + 1])
        del args[k:k + 2]
    build(Path(args[0]), Path(args[1]), cards)
