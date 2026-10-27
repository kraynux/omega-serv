"""Service lance avec une version du code plus ancienne que celle installee
(retour utilisateur 2026-10-26, craftdark) : apres l'extraction d'une mise a
jour, un rechargement a chaud (SIGHUP) relit la CONFIGURATION mais jamais le
CODE deja charge en memoire - les reglages nouveaux restaient sans effet,
alors que l'interface annoncait "service recharge". Fonction pure : les deux
dates viennent de l'appelant."""
from __future__ import annotations

from datetime import datetime, timedelta

# Marge : un service demarre juste apres l'extraction peut afficher une date
# de demarrage arrondie a la seconde (horloge des ticks noyau).
_TOLERANCE = timedelta(seconds=2)


def runs_older_code(process_started_at: datetime, code_modified_at: datetime) -> bool:
    return process_started_at + _TOLERANCE < code_modified_at
