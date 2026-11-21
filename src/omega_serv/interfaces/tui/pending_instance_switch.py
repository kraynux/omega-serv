"""Module feuille (aucun import de app.py/screens/*) - deliberement
separe pour eviter un cycle d'import : app.py (lit `pending_switch`)
et instances_screen.py (le depose) ont tous deux besoin de cette
dataclass, mais app.py importe home.py qui importe instances_screen.py -
un import direct depuis app.py aurait cree une boucle."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

OPEN_ADMIN_WEB = "admin-web"
OPEN_AFTER_SWITCH_ENV_VAR = "OMEGA_SERV_OPEN_AFTER_SWITCH"
"""Comme OMEGA_SERV_SWITCHED_FROM : seul canal qui traverse os.execv ; consomme des la lecture."""


@dataclass(frozen=True)
class PendingInstanceSwitch:
    """Depose par InstancesScreen sur `OmegaServApp.pending_switch` puis
    lu par `omega_serv/__main__.py` APRES que `App.run()` soit revenu
    (Textual completement arrete, terminal restaure) - l'appel
    `os.execv()` lui-meme n'a jamais lieu ici, jamais depuis
    interfaces.tui/ (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §9
    Phase D)."""

    python_executable: Path
    source_name: str
    open_after: str = ""
    """Ecran a ouvrir apres la bascule (OPEN_ADMIN_WEB : configuration distante, tableau de bord web lot 2) ; vide :
    l'accueil seulement."""
