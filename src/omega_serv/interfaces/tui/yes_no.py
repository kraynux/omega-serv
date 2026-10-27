"""Champs oui/non des formulaires, independants de la langue (OMEGA-SERV_PLAN-DETAILLE_I18N.md, lot 4).

Avant : chaque ecran avait sa propre conversion (`"oui" if x else "non"`, `in ("oui", "true",
"1", "o", "y")` ici, `in ("oui", "yes", "true")` la) - affichage en francais seulement et
saisies acceptees differentes d'un ecran a l'autre. Ici : affichage dans la langue de
l'interface ; en saisie, toujours accepte quelle que soit la langue :
oui/o/yes/y/true/vrai/1 et non/n/no/false/faux/0, plus le oui/non TRADUIT - accents ignores
(« si » vaut « sí »), signes diacritiques hindi aussi (« हां » vaut « हाँ »)."""
from __future__ import annotations

import unicodedata

from omega_serv.core.i18n import _

_ALWAYS_YES = frozenset({"oui", "o", "yes", "y", "true", "vrai", "1"})
_ALWAYS_NO = frozenset({"non", "n", "no", "false", "faux", "0"})


def yes() -> str:
    return _("oui")


def no() -> str:
    return _("non")


def to_text(value: bool) -> str:
    return yes() if value else no()


def _normalized(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.strip().lower())
    return "".join(
        char for char in decomposed
        if not unicodedata.combining(char) and unicodedata.category(char) != "Mn"
    )


def is_yes(text: str) -> bool:
    value = _normalized(text)
    return value in _ALWAYS_YES or value == _normalized(yes())


def is_no(text: str) -> bool:
    value = _normalized(text)
    return value in _ALWAYS_NO or value == _normalized(no())
