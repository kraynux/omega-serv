# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de lecture des evenements de ban omega-fire
(plan_active_defense_omega_serv.md, section "Integration omega-fire") -
volontairement en lecture seule, omega-fire demeure la source
d'autorite pour les bans reseau. AUCUNE implementation reelle tant
qu'omega-fire n'expose pas lui-meme une surface de lecture stable (ni
JSONL, ni table SQLite dediee, ni socket n'existent aujourd'hui cote
omega-fire, verifie dans le code reel) - seul un double de test exerce
ce port avant cette phase de maturite."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from omega_serv.domain.security.active_defense.entities import FirewallEvent


class OmegaFireEventsPort(Protocol):
    def recent_events(self, subject_ip: str, since: datetime) -> list[FirewallEvent]:
        ...
