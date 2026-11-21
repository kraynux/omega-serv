# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ce que l'ecran Configuration distante demande a la machine (lot 8, tout le parcours dans la TUI) : essai d'ecoute,
noms et adresses pour le certificat, pare-feu actif, droits du groupe du service sur le certificat."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

LISTEN_IN_USE = "in_use"
LISTEN_NO_ADDRESS = "no_address"
LISTEN_DENIED = "denied"

SHARE_NO_GROUP = "no_group"
"""Le groupe du service n'existe pas (pas de service installe) : le serveur tourne sous votre compte, rien a faire."""
SHARE_NEEDS_PRIVILEGE = "needs_privilege"
"""Votre session n'a pas (encore) le groupe : il faut sudo."""


@dataclass(frozen=True)
class FirewallOpening:
    """Reponse d'`omega-fire.sh port ouvrir` (sous-lot 8b)."""

    ok: bool
    lines: tuple[tuple[str, str, str], ...] = ()
    """(pare-feu, reseau, etat) ; etat : ajoutee, deja, ignoree, echec."""
    error: str = ""


class AdminWebSetupPort(Protocol):
    def can_listen(self, bind: str, port: int) -> str:
        """"" si l'ecoute est possible maintenant, sinon LISTEN_IN_USE, LISTEN_NO_ADDRESS, LISTEN_DENIED ou le message
        d'erreur du systeme."""
        ...

    def machine_names(self) -> tuple[str, tuple[str, ...]]:
        """Nom de la machine et ses adresses IP (boucle locale comprise), pour le certificat."""
        ...

    def active_firewall(self) -> str:
        """Nom du pare-feu actif (ufw, firewalld, nftables), "" si aucun n'est detecte."""
        ...

    def linked_firewall(self, project_root: Path) -> str:
        """Sous-lot 8b (auteur, 2026-11-17) : lanceur d'omega-fire (omega-fire.sh) si omega-fire ET cette instance sont
        inscrits dans le registre de la zone omega-connect (zone active) ; "" sinon (pare-feu seulement signale)."""
        ...

    def open_firewall_port(self, launcher: str, port: int, sources: tuple[str, ...], label: str) -> FirewallOpening:
        """`omega-fire.sh port ouvrir` sous sudo (invite par-dessus la TUI suspendue) ; JSON lu."""
        ...

    def share_with_group(self, directories: tuple[Path, ...], key: Path, certificate: Path, group: str, *,
                         privileged: bool) -> str:
        """Dossiers 750, cle 640, certificat 644, groupe `group`. "" si fait, SHARE_NO_GROUP, SHARE_NEEDS_PRIVILEGE
        (sans `privileged`) ou le message d'erreur."""
        ...
