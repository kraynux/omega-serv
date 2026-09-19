"""Bandeau texte OMEGA-SERV affiche en haut de screens/home.py. Logo
fourni par l'utilisateur (~/DEV/SERV/ascci.txt, lignes 47-49 - caracteres
non modifies), meme convention que le reste de la suite omega- (jamais
de logo invente ici, voir widgets/splash_hero.py). Couleur par jetons de
theme Rich/Textual (`$accent`=vif, `$foreground`=clair) directement dans
le markup - reactif au changement de theme, meme mecanisme que
widgets/splash_hero.py. Regle de couleur donnee par l'utilisateur :
"OMEGA-SERV (texte) ligne 1 VIF, ligne 2 Clair, Ligne 3 vif"."""
from __future__ import annotations

from textual.widgets import Static

_WORDMARK_LINES = (
    "┌╦═══╦┐ ┌╦═╦═╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌╦═══╦┐   ┌╦═══╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌╗   ╔┐",
    "│║   ║│ │║ ║ ║│ ├╬══    │║  ═╦┐ ├╬═══╬┤ ═ └╩═══╦┐ ├╬══    │╠══╦╩┘ │╚╗ ╔╝│",
    "└╩═══╩┘ └╩   ╩┘ └╩═══╩┘ └╩═══╩┘ └╩   ╩┘   └╩═══╩┘ └╩═══╩┘ └╩  ╚═┘ └═╩═╩═┘",
)
"""OMEGA-SERV en un seul bandeau de lettres, fourni par l'utilisateur
(~/DEV/SERV/ascci.txt), caracteres non modifies."""

_MARKUP = "\n".join((
    f"[$accent]{_WORDMARK_LINES[0]}[/]",
    f"[$foreground]{_WORDMARK_LINES[1]}[/]",
    f"[$accent]{_WORDMARK_LINES[2]}[/]",
))


class HomeWordmark(Static):
    """Bandeau decoratif centre en haut de screens/home.py."""

    def __init__(self) -> None:
        super().__init__(_MARKUP, classes="omega-home-wordmark")
