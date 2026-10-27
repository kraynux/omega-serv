"""Demande de redemarrage de l'interface apres un changement de langue
(OMEGA-SERV_PLAN-DETAILLE_I18N.md §5.4). Module feuille, meme raison que
pending_instance_switch.py (eviter un cycle d'import app.py <-> settings_screen.py).

Deposee sur `OmegaServApp.pending_restart` par l'ecran Options, lue par
`omega_serv/__main__.py` APRES `App.run()` : os.execv() relance le MEME Python sur la MEME
installation, nouveau processus = nouvelle langue chargee depuis le disque. Le service
systemd, processus distinct, n'est jamais touche."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingInterfaceRestart:
    language_code: str
