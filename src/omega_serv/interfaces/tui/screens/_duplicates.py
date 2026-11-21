# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Doublons dans les listes de la Configuration detaillee (lot V, decision de l'auteur du 2026-11-15) : avant, deux
alias, redirections ou zones au meme prefixe s'enregistraient sans un mot, et seule la premiere servait."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from omega_serv.core.i18n import _

T = TypeVar("T")


def duplicate_error(existing: Sequence[T], candidate: T, key: Callable[[T], object], label: str,
                    skip_index: int | None = None) -> str | None:
    """Message si `candidate` a la meme cle qu'une AUTRE entree (`skip_index` : celle qu'on modifie)."""
    wanted = key(candidate)
    for index, item in enumerate(existing):
        if index != skip_index and key(item) == wanted:
            return _("Doublon : {label} existe déjà (ligne {line}). Modifiez cette ligne plutôt que d'en ajouter "
                     "une seconde.").format(label=label, line=index + 1)
    return None
