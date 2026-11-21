# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Etat du partage de var/ avec le compte du service (ecran Service, ligne « Permissions », decision de l'auteur du
2026-11-15 : verifier automatiquement, en lecture seule, et n'activer « Reparer » que si quelque chose est faux)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharedAccessReport:
    group_exists: bool
    checked: int
    wrong: tuple[str, ...] = ()
    """Chemins relatifs (quelques-uns au plus) sans le groupe du service ou sans lecture/ecriture de groupe."""
    wrong_count: int = 0
    truncated: bool = False
    """Le parcours s'est arrete a sa limite (tres gros var/) : le resultat ne couvre pas tout."""

    @property
    def ok(self) -> bool:
        return self.group_exists and self.wrong_count == 0
