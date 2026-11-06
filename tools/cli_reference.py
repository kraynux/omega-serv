#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Reference de la CLI - outil de developpement.

  python tools/cli_reference.py           ecrit docs/HELP.md et docs/omega-serv.1
  python tools/cli_reference.py --check   code 1 si l'un des deux n'est plus a jour

Les deux fichiers sont generes depuis le parseur de la CLI (interfaces/cli/main.py::build_parser) :
une commande ou une option ajoutee y apparait sans rien recopier. Relancer apres chaque changement
de commande ; tests/unit/test_cli_reference.py le rappelle. Toujours en francais (langue source).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import tomllib

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from omega_serv.interfaces.cli.command_tree import Command, render_tree, walk
from omega_serv.interfaces.cli.main import build_parser

HELP_MD = PROJECT / "docs" / "HELP.md"
MAN_PAGE = PROJECT / "docs" / "omega-serv.1"
MAN_COLUMNS = 72
"""Arbre de la page de manuel : 80 colonnes moins le retrait de section."""
MARKDOWN_COLUMNS = 100

INTRODUCTION = """\
omega-serv a deux visages :

- **sans argument**, il ouvre l'interface interactive (TUI), qui couvre tout ce qui suit et davantage ;
- **avec une commande**, il travaille en ligne de commande, sans question, pour les scripts, les
  tâches planifiées et le service système.

Toute action de l'interface reste ainsi scriptable. Les commandes sont rangées en groupes
(`config`, `waf`, `riposte`...) ; chaque groupe a ses sous-commandes."""

LAUNCH = """\
Après `install.sh`, trois façons équivalentes de lancer omega-serv :

    <dossier d'installation>/omega-serv.sh <commande>
    serv <commande>                 # alias ajouté par install.sh (nouveau terminal)
    .venv/bin/omega-serv <commande> # dans le dossier d'installation

L'option générale `--config FICHIER` se place **avant** la commande :

    serv --config /chemin/autre.json config check"""

GETTING_HELP = """\
    serv help                      # l'arbre complet des commandes
    serv help riposte              # une seule branche
    serv riposte actions --help    # le détail d'une commande et de ses options
    man omega-serv                 # ce manuel (installé par install.sh)"""

FILES = (
    ("config/omega-serve.json", "Configuration principale (créée par `config init`)."),
    ("config/profiles/", "Profils prêts à l'emploi (`profile list`)."),
    ("secure/auth/", "Utilisateurs et zones protégées (droits 600)."),
    ("secure/certificates/", "Certificats et clés TLS, autorité de certification locale (`ca/`)."),
    ("secure/waf/", "Règles du WAF et scripts Magnet."),
    ("var/log/", "Journaux : accès, erreurs, alertes du WAF."),
    ("var/lib/", "État écrit par le serveur : liste des bans, bases Active Defense et RIPOSTE."),
    ("var/backups/", "Sauvegardes (`config backup`) et anciens certificats."),
    ("var/exports/", "Exports d'incidents (IoC, rapports)."),
    ("var/run/omega-serv.pid", "PID du serveur en marche."),
    ("webroot/", "Le site servi."),
)

ENVIRONMENT = (
    ("OMEGA_SERV_LANG", ("Langue de l'interface pour ce lancement seulement (ex. `OMEGA_SERV_LANG=fr serv`). "
                        "Sans effet sur `serve`, dont les messages restent en français.")),
    ("DO_NOT_TRACK", ("Toute valeur autre que 0 (ex. `DO_NOT_TRACK=1`) : aucun envoi automatique de la "
                     "déclaration anonyme, même avec l'accord donné.")),
)

SIGNALS = (
    ("SIGHUP", ("Recharge les règles WAF et les zones protégées sans couper (= `service reload`). "
               "Bind, port, TLS et moteur demandent un redémarrage.")),
    ("SIGTERM, SIGINT", "Arrêt propre : les connexions en cours se terminent dans le délai de grâce."),
)

EXIT_STATUS = (
    ("0", "Succès."),
    ("1", ("Erreur (configuration invalide, élément introuvable, action refusée...). "
          "Pour `certs verify`/`show`/`check-expiry` : certificat expiré.")),
    ("2", "Erreur d'utilisation (commande ou option inconnue). Pour `audit security` : problème de niveau élevé."),
    ("3", "`audit security` : configuration illisible."),
)
EXIT_STATUS_AUDIT_NOTE = "`audit security` renvoie 1 dès qu'un problème critique est trouvé."

EXAMPLES = (
    ("Vérifier la configuration avant un redémarrage", "serv config check"),
    ("Tester une URL suspecte contre le WAF", "serv waf test --path /index.php --query 'q=<script>alert(1)</script>'"),
    ("Bannir une adresse pendant une heure", "serv blocklist add --network 203.0.113.7 --reason scan --duration-seconds 3600"),
    ("Tout sauvegarder, secrets compris", "serv config backup --all --confirm-secrets --description \"avant mise à jour\""),
    ("Voir les dernières décisions de RIPOSTE, expliquées", "serv riposte decisions list --limit 10 --explain"),
    ("Audit de sécurité en JSON pour un script", "serv audit security --format json --min-severity high"),
)


def _version() -> str:
    return tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def _usage(command: Command) -> str:
    parts = ["omega-serv", *command.path]
    if command.is_group:
        parts.append("COMMANDE")
    for argument in command.arguments:
        if argument.names.startswith("-"):
            parts.append(argument.names if argument.required else f"[{argument.names}]")
        else:
            parts.append(argument.names)
    return " ".join(parts)


def _top_arguments(parser: argparse.ArgumentParser) -> list[tuple[str, str]]:
    return [(", ".join(a.option_strings) + (f" {a.metavar}" if a.metavar else ""), a.help or "")
            for a in parser._actions if a.option_strings and not isinstance(a, argparse._HelpAction)]


# ---------------------------------------------------------------- HELP.md

def render_markdown(parser: argparse.ArgumentParser) -> str:
    commands = walk(parser)
    groups = [c for c in commands if len(c.path) == 1]
    out = [
        f"# omega-serv {_version()} : aide de la ligne de commande",
        "",
        "> Fichier généré par `tools/cli_reference.py` depuis le code : ne pas le modifier à la main.",
        "",
        INTRODUCTION,
        "",
        "## Lancer omega-serv",
        "",
        LAUNCH,
        "",
        "## Obtenir de l'aide",
        "",
        GETTING_HELP,
        "",
        "## Option générale",
        "",
        "| Option | Rôle |",
        "|---|---|",
        *(f"| `{names}` | {text} |" for names, text in _top_arguments(parser)),
        "",
        "## Structure des commandes",
        "",
        "```text",
        *(render_tree(parser, columns=MARKDOWN_COLUMNS) or []),
        "```",
        "",
        "## Sommaire",
        "",
        *(f"- [`{g.path[0]}`](#{g.path[0]}) : {g.text}" for g in groups),
        "",
    ]
    for command in commands:
        level = "##" if len(command.path) == 1 else "###"
        heading = command.path[0] if len(command.path) == 1 else " ".join(command.path)
        out += [f"{level} {heading}", "", command.text]
        if command.details:
            out += ["", command.details]
        out += ["", "```text", _usage(command), "```", ""]
        if command.arguments:
            out += ["| Argument | Rôle |", "|---|---|"]
            for argument in command.arguments:
                required = " **(obligatoire)**" if argument.required else ""
                out.append(f"| `{argument.names}` | {argument.text}{required} |")
            out.append("")
    out += [
        "## Fichiers",
        "",
        "Chemins relatifs au dossier d'installation.",
        "",
        "| Chemin | Contenu |",
        "|---|---|",
        *(f"| `{path}` | {text} |" for path, text in FILES),
        "",
        "## Variables d'environnement",
        "",
        "| Variable | Effet |",
        "|---|---|",
        *(f"| `{name}` | {text} |" for name, text in ENVIRONMENT),
        "",
        "## Signaux (serveur en marche)",
        "",
        "| Signal | Effet |",
        "|---|---|",
        *(f"| `{name}` | {text} |" for name, text in SIGNALS),
        "",
        "## Codes de sortie",
        "",
        "| Code | Sens |",
        "|---|---|",
        *(f"| {code} | {text} |" for code, text in EXIT_STATUS),
        "",
        EXIT_STATUS_AUDIT_NOTE,
        "",
        "## Exemples",
        "",
    ]
    for title, line in EXAMPLES:
        out += [f"{title} :", "", f"    {line}", ""]
    out += ["## Voir aussi", "",
            "`docs/guide.md` (guide complet), `README.md`, la touche F1 dans l'interface.", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- omega-serv.1

def _roff(text: str) -> str:
    """Texte brut -> roff : antislash, tirets d'option, point ou apostrophe en debut de ligne."""
    text = text.replace("\\", "\\e").replace("-", "\\-").replace("`", "")
    return "\\&" + text if text.startswith((".", "'")) else text


def _roff_names(names: str) -> str:
    head, _, rest = names.partition(" ")
    return f"\\fB{_roff(head)}\\fR" + (f" \\fI{_roff(rest)}\\fR" if rest else "")


def render_man(parser: argparse.ArgumentParser) -> str:
    commands = walk(parser)
    out = [
        '.\\" -*- coding: UTF-8 -*-',
        '.\\" Genere par tools/cli_reference.py depuis le code : ne pas modifier a la main.',
        ".nr HY 0",
        ".ds AD l",
        f'.TH OMEGA\\-SERV 1 "" "omega\\-serv {_version()}" "Commandes utilisateur"',
        ".nh",
        ".ad l",
        ".SH NOM",
        "omega\\-serv \\- serveur web sécurisé (WAF, TLS, RIPOSTE, Active Defense)",
        ".SH SYNOPSIS",
        ".B omega\\-serv",
        ".br",
        ".B omega\\-serv",
        "[\\fB\\-\\-config\\fR \\fIFICHIER\\fR] \\fICOMMANDE\\fR [\\fISOUS\\-COMMANDE\\fR] [\\fIOPTIONS\\fR]",
        ".br",
        ".B omega\\-serv help",
        "[\\fICOMMANDE\\fR ...]",
        ".SH DESCRIPTION",
    ]
    for paragraph in INTRODUCTION.split("\n\n"):
        for line in paragraph.splitlines():
            if line.startswith("- "):
                out += [".IP \\(bu 2", _roff(line[2:].replace("**", ""))]
            else:
                out.append(_roff(line.strip().replace("**", "")))
        out.append(".PP")
    out += [
        ("Lancement : \\fBomega\\-serv.sh\\fR dans le dossier d'installation, ou l'alias \\fBserv\\fR "
        "ajouté par \\fBinstall.sh\\fR."),
        ".SH OPTION GÉNÉRALE",
    ]
    for names, text in _top_arguments(parser):
        out += [".TP", _roff_names(names), _roff(text)]
    out += [".SH STRUCTURE", ".nf", *(_roff(line) for line in render_tree(parser, columns=MAN_COLUMNS) or []), ".fi", ".SH COMMANDES"]
    for command in commands:
        if len(command.path) == 1:
            out += [f".SS {_roff(command.path[0])}", _roff(command.text)]
            if command.details:
                out += [".PP", _roff(command.details)]
            if command.is_group:
                continue
        else:
            out += [".TP", f"\\fB{_roff(' '.join(command.path))}\\fR", _roff(command.text)]
            if command.details:
                out += [".br", _roff(command.details)]
        if command.arguments:
            out.append(".RS")
            for argument in command.arguments:
                required = " (obligatoire)" if argument.required else ""
                out += [".TP", _roff_names(argument.names), _roff(argument.text + required)]
            out.append(".RE")
    out.append(".SH FICHIERS")
    out.append("Chemins relatifs au dossier d'installation.")
    for path, text in FILES:
        out += [".TP", f"\\fI{_roff(path)}\\fR", _roff(text)]
    out.append(".SH ENVIRONNEMENT")
    for name, text in ENVIRONMENT:
        out += [".TP", f"\\fB{_roff(name)}\\fR", _roff(text)]
    out.append(".SH SIGNAUX")
    for name, text in SIGNALS:
        out += [".TP", f"\\fB{_roff(name)}\\fR", _roff(text)]
    out.append(".SH CODES DE SORTIE")
    for code, text in EXIT_STATUS:
        out += [".TP", f"\\fB{code}\\fR", _roff(text)]
    out += [".PP", _roff(EXIT_STATUS_AUDIT_NOTE), ".SH EXEMPLES"]
    for title, line in EXAMPLES:
        out += [".PP", _roff(title) + " :", ".RS", ".nf", _roff(line), ".fi", ".RE"]
    out += [".SH VOIR AUSSI",
            "\\fIdocs/HELP.md\\fR, \\fIdocs/guide.md\\fR, \\fIREADME.md\\fR ; la touche F1 dans l'interface."]
    return "\n".join(out) + "\n"


def main() -> int:
    check = "--check" in sys.argv[1:]
    parser = build_parser()
    stale = []
    for path, content in ((HELP_MD, render_markdown(parser)), (MAN_PAGE, render_man(parser))):
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(PROJECT))
        else:
            path.write_text(content, encoding="utf-8")
            print(f"écrit : {path.relative_to(PROJECT)}")
    if stale:
        print("pas à jour : " + ", ".join(map(str, stale)) + " - lancer tools/cli_reference.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
