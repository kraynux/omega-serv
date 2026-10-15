"""Les 3 viewers de l'ecran "Voir les logs" (gestion des logs, refonte
menu 2026-10-15, porte depuis omega-log/plan_omega_log.md §2/§3) :
SIMPLE (tail en direct + stats generiques, nouveau pour Omega-Serv),
CLASSIC (lecture + suivi deja existant, `LogViewerScreen`, generalise a
un chemin arbitraire), LNAV (fusion multi-logs, deja existant,
`LnavScreen`). Regle de selection : 1 log -> les 3 disponibles ; 2+
logs -> LNAV uniquement (seul capable de fusionner plusieurs fichiers)."""
from __future__ import annotations

from enum import Enum


class ViewerType(Enum):
    SIMPLE = "simple"
    CLASSIC = "classic"
    LNAV = "lnav"


def allowed_viewers(log_count: int) -> tuple[ViewerType, ...]:
    if log_count <= 1:
        return (ViewerType.SIMPLE, ViewerType.CLASSIC, ViewerType.LNAV)
    return (ViewerType.LNAV,)
