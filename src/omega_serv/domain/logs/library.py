"""Entites de la Bibliotheque de logs (gestion des logs, refonte menu
2026-10-15, porte depuis omega-log/plan_omega_log.md §3/§10) - hub
central referencant les logs a traiter. Alimentation MANUELLE
uniquement pour cette passe (import au detail via un scan automatique
du type "Registre" d'omega-log explicitement differe, YAGNI tant
qu'aucun besoin reel confirme) - un chemin est ajoute a la main depuis
l'ecran Bibliotheque.

Pures donnees de domaine, aucune I/O ici : la lecture disque reelle
(existence/taille/mtime) est faite par `application/logs/library.py`,
jamais par ces entites elles-memes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LogFile:
    """Un chemin de log, avec son etat au moment de la derniere
    consultation de la Bibliotheque (jamais fige a l'ajout - voir
    `LibraryRecord`)."""

    path: str
    access: str = "file"
    service_id: str | None = None
    exists: bool = False
    size_bytes: int | None = None
    modified_at: datetime | None = None
    note: str = ""

    @property
    def is_stale(self) -> bool:
        """Fichier present mais vide - candidat probablement mort
        (service arrete/log herite), ne doit jamais etre presente au
        meme rang qu'un fichier reellement alimente."""
        return self.exists and self.size_bytes == 0


@dataclass(frozen=True, slots=True)
class LibraryRecord:
    """Entree PERSISTEE de la Bibliotheque - identite seule (path/
    access/service_id), jamais l'etat au moment de l'ajout : la
    fraicheur est toujours recalculee a l'affichage
    (application/logs/library.py::refresh_log_file), jamais figee dans
    le stockage JSON."""

    path: str
    access: str = "file"
    service_id: str | None = None
