# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Bans connus ailleurs sur la machine (plan_active_defense_omega_serv.md, section "Integration omega-fire" ;
plan omega-connect, phase 3, 2026-11-21) - lecture seule : omega-fire et fail2ban (action d'omega-jail) restent
les seules autorites des bans reseau ; ils publient leurs bans dans le journal des bans de la zone omega-synchro.

Remplace le contrat `OmegaFireEventsPort` (jamais implemente : omega-fire n'exposait rien) par la seule question
qu'Active Defense pose reellement : cette adresse est-elle bannie ailleurs en ce moment ?"""
from __future__ import annotations

from typing import Protocol


class KnownBansPort(Protocol):
    def is_banned(self, ip: str) -> bool:
        """Vrai si l'adresse est couverte par un ban actif publie par un autre outil (jamais par un jail RIPOSTE
        d'omega-serv lui-meme : anti-boucle). Jamais une exception : faux si rien n'est lisible."""
        ...
