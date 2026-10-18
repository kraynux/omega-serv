"""Acces en LECTURE SEULE aux listes de reference livrees avec omega-serv
(OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.11) - jamais chargees par le
serveur : elles servent de modele au premier chargement et de source aux
"Nouveautes de la reference"."""
from __future__ import annotations

from typing import Protocol


class KeywordReferencePort(Protocol):
    def names(self) -> tuple[str, ...]:
        """Noms de fichier des references disponibles (ex. sensitive-paths-hostile.txt)."""
        ...

    def read(self, name: str) -> str | None:
        """Contenu d'une reference, None si elle n'existe pas."""
        ...
