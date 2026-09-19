"""Modele de contenu du guide d'aide (OMEGA-SERV_PLAN-DETAILLE_GUIDE_AIDE.md
§3.2) - donnees pures, aucune dependance Textual ici (seul l'ecran de
rendu, guide_detail_screen.py, en a besoin) : verifiable par mypy/tests
comme le reste du projet, jamais un format de fichier externe a parser.

Une fiche par ecran (`ScreenGuide`) suit toujours le meme gabarit (§4 du
plan) : Definition/Parcours, puis par champ Definition/Utilisation/
Action/Reaction, puis Consequences et Points de vigilance au niveau de
l'ecran - jamais une structure ad hoc differente d'une fiche a l'autre,
c'est ce qui rend le guide lisible une fois qu'on a compris une fiche."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldGuide:
    label: str
    definition: str
    utilisation: str
    action: str
    reaction: str


@dataclass(frozen=True)
class ScreenGuide:
    screen_class_name: str
    """Nom exact de la classe d'ecran reelle (`type(self).__name__`) -
    seule cle de resolution (registry.py), jamais un identifiant
    invente separement qui pourrait diverger du vrai nom de classe."""
    title: str
    acces: str
    definition: str
    fields: tuple[FieldGuide, ...] = field(default_factory=tuple)
    consequences: str = ""
    points_de_vigilance: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FaqEntry:
    category: str
    question: str
    answer: str
