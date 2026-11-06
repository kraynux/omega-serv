"""Arbre des commandes de la CLI : source unique de `omega-serv help`, de docs/HELP.md et de la page
de manuel docs/omega-serv.1 (generees par tools/cli_reference.py depuis le meme parseur, jamais
recopiees a la main). Chaque commande et chaque option porte son texte d'aide dans le parseur."""
from __future__ import annotations

import argparse
import shutil
import textwrap
from dataclasses import dataclass

from omega_serv.core.i18n import _


def add_command(
    subparsers: argparse._SubParsersAction, name: str, text: str, details: str = "",
) -> argparse.ArgumentParser:
    """Commande terminale ou groupe : `text` sert a la liste du parent et a son propre --help, `details`
    complete seulement ce --help (et le manuel)."""
    parser: argparse.ArgumentParser = subparsers.add_parser(name, help=text, description=f"{text} {details}".strip())
    return parser


def add_group(
    subparsers: argparse._SubParsersAction, name: str, text: str, dest: str, details: str = "",
) -> argparse._SubParsersAction:
    return add_command(subparsers, name, text, details).add_subparsers(
        dest=dest, required=True, title=_("commandes"), metavar=_("COMMANDE"),
    )


@dataclass(frozen=True)
class Argument:
    names: str
    """« --network RESEAU », « id »..."""
    text: str
    required: bool


@dataclass(frozen=True)
class Command:
    path: tuple[str, ...]
    text: str
    details: str
    arguments: tuple[Argument, ...]
    is_group: bool


def _sub_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    return next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)


def _argument_label(action: argparse.Action) -> str:
    metavar = action.metavar
    if metavar is None and action.choices is not None:
        metavar = "{" + ",".join(str(c) for c in action.choices) + "}"
    if metavar is None:
        metavar = action.dest.upper().replace("_", "-")
    if not action.option_strings:
        return f"{metavar} ..." if action.nargs in ("*", "+") else str(metavar)
    if action.nargs == 0:
        return ", ".join(action.option_strings)
    suffix = f" {metavar} ..." if action.nargs in ("*", "+") else f" {metavar}"
    return ", ".join(action.option_strings) + suffix


def _arguments(parser: argparse.ArgumentParser) -> tuple[Argument, ...]:
    return tuple(
        Argument(_argument_label(a), a.help or "", bool(a.required) and bool(a.option_strings))
        for a in parser._actions
        if not isinstance(a, (argparse._HelpAction, argparse._SubParsersAction)) and a.help != argparse.SUPPRESS
    )


def walk(parser: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> list[Command]:
    """Toutes les commandes, dans l'ordre de declaration (parcours en profondeur)."""
    commands: list[Command] = []
    sub = _sub_action(parser)
    if sub is None:
        return commands
    texts = {choice.dest: choice.help or "" for choice in sub._choices_actions}
    for name, child in sub.choices.items():
        child_path = (*path, name)
        is_group = _sub_action(child) is not None
        text = texts.get(name, "")
        details = (child.description or "")[len(text):].strip()
        commands.append(Command(child_path, text, details, _arguments(child), is_group))
        commands.extend(walk(child, child_path))
    return commands


def render_tree(
    parser: argparse.ArgumentParser, branch: tuple[str, ...] = (), columns: int = 0,
) -> list[str] | None:
    """Arbre lisible au terminal, descriptions repliees a `columns` (0 : jamais) ; None si `branch` ne
    designe aucune commande."""
    commands = walk(parser)
    if branch and not any(c.path == branch for c in commands):
        return None
    selected = [c for c in commands if c.path[:len(branch)] == branch]
    width = max((2 * (len(c.path) - 1) + len(c.path[-1]) for c in selected), default=0) + 2
    lines = []
    for command in selected:
        label = "  " * (len(command.path) - 1) + command.path[-1]
        wrapped = textwrap.wrap(command.text, columns - width) if columns - width >= 30 else [command.text]
        lines.append(label.ljust(width) + (wrapped[0] if wrapped else ""))
        lines.extend(" " * width + rest for rest in wrapped[1:])
    return lines


def cmd_help(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    branch = tuple(args.branch)
    lines = render_tree(parser, branch, shutil.get_terminal_size().columns)
    if lines is None:
        print(_("Commande inconnue : {command}").format(command=" ".join(branch)))
        return 1
    print(_("Commandes d'omega-serv (détail d'une commande : omega-serv <commande> --help) :"))
    print()
    for line in lines:
        print(line)
    return 0
