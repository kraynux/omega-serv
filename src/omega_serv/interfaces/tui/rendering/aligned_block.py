"""Blocs de texte alignes, independants de la langue (OMEGA-SERV_PLAN-DETAILLE_I18N.md, lot 4).

Avant : libelles alignes par des espaces tapes a la main ("  Statut  : ") et titres de blocs a
cadre de longueur fixe ("── CLIENTS ───...") - justes en francais seulement. Ici l'alignement
est CALCULE sur le libelle le plus long du bloc, dans la langue affichee, en largeur d'ecran
reelle (rich.cells.cell_len : un caractere chinois occupe deux colonnes)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from rich.cells import cell_len
from rich.text import Text

from omega_serv.core.i18n import _

SECTION_WIDTH = 28
"""Largeur des titres de blocs, cadre compris (celle des anciens titres figes)."""
_INDENT = "  "
_SEPARATOR = " : "


def section_title(title: str, width: int = SECTION_WIDTH) -> str:
    """'── TITRE ' complete par des traits jusqu'a `width` colonnes (jamais moins de 3 traits)."""
    head = f"── {title} "
    return head + "─" * max(3, width - cell_len(head)) + "\n"


def centered_section_title(title: str, width: int) -> str:
    """'─── TITRE ───' centre sur `width` colonnes (largeur reelle du cadre, ecran Etat & Ressources
    2026-11-05) ; jamais moins de 3 traits de chaque cote."""
    middle = f" {title} "
    room = max(6, width - cell_len(middle))
    return "─" * (room // 2) + middle + "─" * (room - room // 2) + "\n"


def _pad(label: str, width: int) -> str:
    return label + " " * max(0, width - cell_len(label))


@dataclass
class _Row:
    label: str
    value: str | Text
    style: str | None
    details: list[tuple[str, str | None]] = field(default_factory=list)
    free: bool = False


class AlignedBlock:
    """Lignes 'libelle : valeur' d'un meme bloc, alignees sur le libelle le plus long.
    `detail()` ajoute une ligne sous la valeur precedente, alignee sur sa colonne."""

    def __init__(self) -> None:
        self._rows: list[_Row] = []

    def row(self, label: str, value: str | Text, style: str | None = None) -> AlignedBlock:
        self._rows.append(_Row(label, value, style))
        return self

    def apply(self, add: Callable[[AlignedBlock], None]) -> AlignedBlock:
        """Laisse une fonction ajouter des lignes sans casser l'enchainement (graphique sous une ligne)."""
        add(self)
        return self

    def line(self, text: Text) -> AlignedBlock:
        """Ligne libre sous la precedente (graphique), en retrait mais hors alignement des libelles."""
        self._rows.append(_Row("", text, None, free=True))
        return self

    def detail(self, text: str, style: str | None = "dim") -> AlignedBlock:
        if not self._rows:
            raise ValueError(_("detail() sans ligne precedente"))
        self._rows[-1].details.append((text, style))
        return self

    def render_into(self, content: Text) -> Text:
        width = max((cell_len(r.label) for r in self._rows if not r.free), default=0)
        value_column = " " * (len(_INDENT) + width + len(_SEPARATOR))
        for r in self._rows:
            if r.free:
                content.append(_INDENT)
                content.append_text(r.value if isinstance(r.value, Text) else Text(r.value))
                content.append("\n")
                continue
            if isinstance(r.value, Text):  # valeur deja stylee (jauge coloree) : seul le libelle prend `style`
                content.append(f"{_INDENT}{_pad(r.label, width)}{_SEPARATOR}", style=r.style)
                content.append_text(r.value)
                content.append("\n")
            else:
                content.append(f"{_INDENT}{_pad(r.label, width)}{_SEPARATOR}{r.value}\n", style=r.style)
            for text, style in r.details:
                content.append(f"{value_column}{text}\n", style=style)
        return content
