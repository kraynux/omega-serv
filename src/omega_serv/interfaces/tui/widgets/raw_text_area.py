"""Zone de texte SANS raccourcis clavier (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_
PATHS.md §3.6, annexe B - decision utilisateur 2026-10-18 : "pas de
raccourcis clavier, trop de risque de telescopage avec les raccourcis des
utilisateurs qui different, seules les saisies brutes pour le clavier").

Le `TextArea` de Textual embarque 33 raccourcis (ctrl+z/y, ctrl+x/c/v,
ctrl+k, ctrl+u, ctrl+w, ctrl+a/e, ctrl+d, F6, F7, alt+..., shift+...).
`inherit_bindings=False` les retire TOUS ; on ne redeclare que les touches de
saisie brute : fleches, Debut/Fin, Page prec./suiv., Retour arriere, Suppr.
Les caracteres imprimables et Entree sont geres nativement par le widget
(pas des raccourcis). Toute autre action (annuler, couper, coller,
selectionner...) passe par un BOUTON de l'ecran. Verifie le 2026-10-18
(Pilot) : `q t a o r` tapes dans ce widget vont dans le texte, jamais vers
les raccourcis globaux de l'application."""
from __future__ import annotations

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import TextArea

RAW_EDITING_KEYS: tuple[str, ...] = (
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown", "backspace", "delete",
)


def _raw_bindings() -> list[BindingType]:
    kept: list[BindingType] = []
    for binding in TextArea.BINDINGS:
        if not isinstance(binding, Binding):
            continue
        keys = [key for key in binding.key.split(",") if key.strip() in RAW_EDITING_KEYS]
        if keys:
            kept.append(Binding(",".join(keys), binding.action, binding.description, show=False))
    return kept


class RawTextArea(TextArea, inherit_bindings=False):
    BINDINGS: ClassVar[list[BindingType]] = _raw_bindings()
