"""Generation des listes de REFERENCE livrees avec omega-serv depuis le
fichier maitre de developpement (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md
§3.11 : fichier maitre -> reference livree -> fichier local de
l'utilisateur, jamais l'inverse, jamais de fusion automatique).

Appele par build-release.sh (outil de developpement, jamais par le serveur) :
    python -m omega_serv.infrastructure.waf.keyword_reference_generator <maitre> <dossier_references>

Le maitre est decoupe en blocs `#== HOSTILE (...) ==`, `#== SONDAGE (...) ==`,
`#== EXCLU (...) ==` ; les titres de section (`#Titre`) sont conserves dans
les references. Une reference qui produirait la moindre erreur de validation
(validateur unique, keyword_list.py) fait ECHOUER la generation : jamais
une reference cassee livree."""
from __future__ import annotations

import sys
from pathlib import Path

from omega_serv.domain.security.waf.keyword_list import (
    PATH_LIST_SYNTAX_HELP,
    analyze_path_list_text,
)

SYNTAX_HELP = PATH_LIST_SYNTAX_HELP

_BLOCKS = {"HOSTILE": "hostile", "SONDAGE": "sondage", "EXCLU": "exclu"}

REFERENCES = (
    {
        "block": "hostile",
        "name": "sensitive-paths-hostile",
        "anchor": "any_segment",
        "description": "{count} chemins sans usage légitime connu (secrets, sauvegardes, VCS, consoles...).",
        "advice": "gravité Élevée (6, bloque dès le 1er accès), recherche n'importe où dans le chemin, "
                  "récidive 2 accès en 10 min -> ban 24 h. 1er chargement conseillé en Observation.",
    },
    {
        "block": "sondage",
        "name": "sensitive-paths-probe",
        "anchor": "root",
        "description": "{count} chemins de sondage courants, mais parfois servis par un vrai site "
                       "(admin, API, supervision...).",
        "advice": "gravité Moyenne (3, ne bloque jamais seule), recherche au début du chemin, "
                  "récidive 5 accès en 10 min -> ban 1 h. 1er chargement conseillé en Observation.",
    },
)


def split_master(text: str) -> dict[str, list[tuple[str, list[str]]]]:
    """bloc -> [(titre de section, entrees)] dans l'ordre du maitre."""
    blocks: dict[str, list[tuple[str, list[str]]]] = {name: [] for name in _BLOCKS.values()}
    current_block: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#=="):
            keyword = line[3:].strip().split(" ", 1)[0]
            current_block = _BLOCKS.get(keyword)
            continue
        if current_block is None:
            continue  # en-tete du maitre
        if line.startswith("#") and not line.startswith("# /"):
            blocks[current_block].append((line[1:].strip(), []))
            continue
        entry = line[2:] if line.startswith("# /") else line  # entrees EXCLU commentees
        if not blocks[current_block]:
            blocks[current_block].append(("", []))
        blocks[current_block][-1][1].append(entry)
    return blocks


def render_reference(reference: dict[str, str], sections: list[tuple[str, list[str]]]) -> str:
    count = sum(len(entries) for _, entries in sections)
    lines = [
        f"# omega-serv - liste de référence : {reference['name']}",
        "# " + reference["description"].format(count=count),
        f"# Réglages conseillés : {reference['advice']}",
        "# Fichier de RÉFÉRENCE (lecture seule, remplacé à chaque mise à jour d'omega-serv).",
        "# Il n'est jamais chargé tel quel : l'assistant WAF Custom en crée une copie",
        "# locale modifiable dans secure/waf/rules/keywords/ au premier chargement.",
        "# Généré depuis le fichier maître ~/DEV/JAIL/sensitive-path.txt - ne pas éditer ici.",
        "#", SYNTAX_HELP, "",
    ]
    for title, entries in sections:
        if entries:
            lines.append(f"#{title}")
            lines.extend(entries)
    lines.append("")
    return "\n".join(lines)


def generate(master_text: str) -> dict[str, str]:
    """nom de fichier -> contenu. Leve ValueError si une reference est invalide."""
    blocks = split_master(master_text)
    outputs: dict[str, str] = {}
    for reference in REFERENCES:
        content = render_reference(reference, blocks[reference["block"]])
        errors = analyze_path_list_text(content, reference["anchor"]).errors
        if errors:
            details = " ; ".join(f"ligne {e.line} : {e.message}" for e in errors[:5])
            raise ValueError(f"reference {reference['name']} invalide : {details}")
        outputs[f"{reference['name']}.txt"] = content
    return outputs


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage : keyword_reference_generator <fichier_maitre> <dossier_references>", file=sys.stderr)
        return 2
    master, out_dir = Path(argv[0]), Path(argv[1])
    try:
        outputs = generate(master.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Generation des references impossible : {e}", file=sys.stderr)
        return 1
    for name, content in outputs.items():
        target = out_dir / name
        changed = not target.exists() or target.read_text(encoding="utf-8") != content
        target.write_text(content, encoding="utf-8")
        target.chmod(0o644)
        entries = len(analyze_path_list_text(content, "any_segment").entries)
        print(f"{name} : {entries} entrees{' (mis a jour)' if changed else ' (inchange)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
