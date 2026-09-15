# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de suivi incremental d'un fichier de log (plan interface
§3.4/§8, "tail simple")."""
from __future__ import annotations

from typing import Protocol


class LiveTailPort(Protocol):
    def read_new_lines(self) -> list[str]:
        """Retourne les lignes ajoutees depuis le dernier appel (liste
        vide si rien de nouveau ou fichier absent)."""
        ...
