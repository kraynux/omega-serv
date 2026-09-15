# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Composition ASCII de l'ecran de demarrage. Logo fourni par
l'utilisateur, voir ~/DEV/SERV/ascci.txt - caracteres non modifies.

Alignement : chaque ligne est centree via `str.center(_WIDTH)` (largeur
de la boite OMEGA-SERV, l'element le plus large) plutot que de
reproduire les espaces d'indentation du fichier source - meme technique
que le reste de la suite omega- (omega-check/interfaces/tui/widgets/
splash_hero.py). Contrairement a CHECK, une ligne vide separe le motif
du bas de la tagline (retour utilisateur explicite pour SERV - decision
esthetique differente de celle de CHECK, pas un desaccord avec elle).

Couleur par jetons de theme Rich/Textual (`$accent`=vif, `$foreground`
=clair) directement dans le markup - reactif au changement de theme.
Regles de couleur fournies par l'utilisateur (voir ascii.txt) :
- cadres/"containers" (boites de bordure) : clair.
- texte "LINUX WEB-SERVER" : vif (meme convention que "LINUX SERVER
  CHECK" chez CHECK - le cadre reste clair, seul le texte interieur
  change).
- bandeau OMEGA-SERV (3 lignes, dans sa boite) : vif / clair / vif.
- corps du serveur et pied (blocs █▒░▓ entre/sous la boite OMEGA-SERV) :
  seuls les "voyants" (retour utilisateur round 2 : les runs de "█"
  isolees, encadrees d'ombrage des deux cotes, jamais les colonnes de
  bordure ni les segments qui longent tout le bord de la ligne) restent
  vifs - tout le reste (ombrage ▒░▓, colonnes de bordure adjacentes a
  un cadre │╣╠└┐┌┘, segments courant sur toute la largeur de la ligne)
  passe en clair. Degrade a 4 nuances demande par l'utilisateur
  simplifie a 2 tons (seuls `$accent`/`$foreground` existent dans
  `omega_lib.theme.policies.Palette`, meme simplification deja
  acceptee chez CHECK pour sa propre pyramide de blocs ▓░).
- tagline du bas : les "|" separateurs vifs, les mots clairs (meme
  orientation que CHECK, explicitement demandee ici aussi)."""
from __future__ import annotations

from itertools import groupby

from textual.widgets import Static

_WIDTH = 77
"""Largeur de la boite OMEGA-SERV (l'element le plus large) : axe de
centrage commun a tout le logo."""

_FRAME_CHARS = frozenset("│╣╠└┐┌┘")
"""Caracteres de cadre/transition adjacents auxquels une colonne de
bordure "█" peut se trouver accolee (voir _is_border_run)."""


def _centered(line: str) -> str:
    return line.center(_WIDTH)


def _center_markup(markup: str, visible_length: int) -> str:
    """Centre un texte deja colore (markup) sur `_WIDTH`, en calculant le
    remplissage a partir de la longueur VISIBLE d'origine (avant mise en
    forme) - centrer directement la chaine avec des balises `[$accent]`
    fausserait le calcul (les balises comptent comme des caracteres pour
    `str.center`, mais sont invisibles a l'affichage)."""
    padding = max(_WIDTH - visible_length, 0)
    left = padding // 2
    right = padding - left
    return " " * left + markup + " " * right


def _split_frame(line: str, frame_char: str = "│") -> str:
    """Ligne du type '│ texte │' (deja centree) -> cadre clair, texte vif."""
    prefix, _, rest = line.partition(frame_char)
    inner, _, suffix = rest.rpartition(frame_char)
    return f"{prefix}[$foreground]{frame_char}[/][$accent]{inner}[/][$foreground]{frame_char}{suffix}[/]"


def _wordmark_line(line: str, color: str, frame_char: str = "│") -> str:
    """Ligne du bandeau OMEGA-SERV a l'interieur de sa boite : cadre
    clair, contenu dans la couleur demandee (vif/clair selon la ligne)."""
    prefix, _, rest = line.partition(frame_char)
    inner, _, suffix = rest.rpartition(frame_char)
    return f"{prefix}[$foreground]{frame_char}[/][{color}]{inner}[/][$foreground]{frame_char}{suffix}[/]"


def _is_border_run(line: str, start: int, end: int) -> bool:
    """Une colonne de "█" est une bordure (clair), pas un voyant (vif),
    si elle : longe tout le bord de la ligne (aucun autre caractere sur
    cette ligne), ou se trouve au tout debut/tout a la fin de la ligne,
    ou est directement accolee a un caractere de cadre (`_FRAME_CHARS`),
    ou fait plus d'UNE colonne de large (retour utilisateur 2026-09-10,
    vrai bug trouve : un run large de "█" non accole a un bord (le badge
    "V1.00" en tete, le pied du serveur) tombait par defaut dans le cas
    "voyant" faute de correspondre a aucune des conditions ci-dessus -
    seules les colonnes ISOLEES D'UNE SEULE LARGEUR sont de vrais
    voyants, jamais un segment large, meme au milieu d'une ligne).
    Seules les colonnes isolees ENTRE deux zones d'ombrage (jamais en
    bordure, jamais plus larges qu'une colonne) sont de vrais voyants -
    retour utilisateur round 2 : initialement toute colonne de "█" etait
    vive, ce qui donnait l'impression que le corps entier du serveur
    etait allume plutot que quelques voyants isoles."""
    if end - start == len(line) or start == 0 or end == len(line):
        return True
    if end - start != 1:
        return True
    return line[start - 1] in _FRAME_CHARS or line[end] in _FRAME_CHARS


def _light_up(line: str) -> str:
    """Colore les voyants ("█" isoles, jamais en bordure) en vif, tout
    le reste en clair - effet de "voyants allumes" a l'interieur du
    corps du serveur (voir _is_border_run pour la distinction)."""
    markup = []
    position = 0
    for is_block, run in groupby(line, key=lambda char: char == "█"):
        text = "".join(run)
        end = position + len(text)
        if is_block and not _is_border_run(line, position, end):
            markup.append(f"[$accent]{text}[/]")
        else:
            markup.append(f"[$foreground]{text}[/]")
        position = end
    return "".join(markup)


def _tagline(line: str) -> str:
    """'HTTP | WAF | ...' -> mots clairs, '|' vifs."""
    parts = line.split("|")
    colored = [f"[$foreground]{part}[/]" for part in parts]
    return "[$accent]|[/]".join(colored)


_LINUX_BOX = (
    "┌─────────────────────┐",
    "│  LINUX WEB-SERVER   │",
    "└─────────────────────┘",
)

_INDICATOR = (
    "▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄",
    "▄████▒V1.00▒████▄",
    "┌█▒░▒░▒░▒░▒░▒░▒░▒█┐",
)

_OMEGA_BOX = (
    "┌───────────────────────────────────────────────────────────────────────────┐",
    "│ ┌╦═══╦┐ ┌╦═╦═╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌╦═══╦┐   ┌╦═══╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌╗   ╔┐ │",
    "│ │║   ║│ │║ ║ ║│ ├╬══    │║  ═╦┐ ├╬═══╬┤ ═ └╩═══╦┐ ├╬══    │╠══╦╩┘ │╚╗ ╔╝│ │",
    "│ └╩═══╩┘ └╩   ╩┘ └╩═══╩┘ └╩═══╩┘ └╩   ╩┘   └╩═══╩┘ └╩═══╩┘ └╩  ╚═┘ └═╩═╩═┘ │",
    "└───────────────────────────────────────────────────────────────────────────┘",
)

_SERVER_BODY = (
    "│█▒░░▓█░░░░░▓█░░▒█│",
    "│█▒░░░░░░░░░░░░░▒█│",
    "╔══════════╣█▒░░█▓░░░░░█▓░░▒█╠══════════╗",
    "┌╦═══╩═══╦┐     │█▒░░░░░░░░░░░░░▒█│     ┌╦═══╩═══╦┐",
    "│║ L A N ║│     │█▒░░▓█░░░░░█▓░░▒█│     │║ W E B ║│",
    "└╩═══════╩┘     └█▒░▒░▒░▒░▒░▒░▒░▒█┘     └╩═══════╩┘",
    "█████████████████",
    "│║▓║│",
    "█▓▒▒▓███████▓▒▒▓█",
)

_TAGLINE = "HTTP | WAF | TLS | LOG | SECURE | AUDIT | EXPORT"

_LINES: tuple[str, ...] = (
    f"[$foreground]{_centered(_LINUX_BOX[0])}[/]",
    _split_frame(_centered(_LINUX_BOX[1])),
    f"[$foreground]{_centered(_LINUX_BOX[2])}[/]",
    *[_center_markup(_light_up(row), len(row)) for row in _INDICATOR],
    f"[$foreground]{_centered(_OMEGA_BOX[0])}[/]",
    _wordmark_line(_centered(_OMEGA_BOX[1]), "$accent"),
    _wordmark_line(_centered(_OMEGA_BOX[2]), "$foreground"),
    _wordmark_line(_centered(_OMEGA_BOX[3]), "$accent"),
    f"[$foreground]{_centered(_OMEGA_BOX[4])}[/]",
    *[_center_markup(_light_up(row), len(row)) for row in _SERVER_BODY],
    "",
    _tagline(_centered(_TAGLINE)),
)

_MARKUP = "\n".join(_LINES)


class SplashHero(Static):
    """Bloc decoratif de l'ecran de demarrage (screens/splash.py)."""

    def __init__(self) -> None:
        super().__init__(_MARKUP, classes="omega-splash-hero")
