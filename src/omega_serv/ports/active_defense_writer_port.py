"""Contrat de l'ecriture differee d'Active Defense (OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_
CHARGE.md §3.6, correctif valide le 2026-10-26).

La boucle asyncio qui sert les visiteurs ne touche plus jamais la base en ecriture : elle depose
un travail (`ActiveDefenseJob`) que UN SEUL fil d'ecriture execute, avec ses propres
repositories (sa propre connexion). Mesure qui l'a justifie : une ecriture SQLite par requete
suspecte faite sur la boucle coutait 18 % de debit aux visiteurs legitimes sous un botnet, et un
verrou externe (purge, sauvegarde) figeait tout le serveur 5 s puis coupait les connexions."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from omega_serv.ports.deception_assignment_repository_port import DeceptionAssignmentRepositoryPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort


@dataclass(frozen=True)
class ActiveDefenseRepositories:
    """Les repositories du FIL D'ECRITURE - jamais utilises depuis la boucle."""
    threat_states: ThreatStateRepositoryPort
    incidents: IncidentRepositoryPort
    deception_assignments: DeceptionAssignmentRepositoryPort


ActiveDefenseJob = Callable[[ActiveDefenseRepositories], None]


class ActiveDefenseWriterPort(Protocol):
    def set_error_reporter(self, report: Callable[[str], None]) -> None:
        """Ou ecrire les incidents d'ecriture (journal d'erreurs du serveur)."""
        ...

    def start(self) -> None:
        ...

    def submit(self, job: ActiveDefenseJob) -> bool:
        """Ne bloque jamais. False si la file est pleine (travail abandonne et compte)."""
        ...

    def flush(self, timeout: float) -> bool:
        """Attend que tout ce qui a ete depose avant l'appel soit ecrit (tests, arret)."""
        ...

    def stop(self, timeout: float) -> None:
        """Ecrit ce qui peut l'etre en `timeout` secondes au plus, puis s'arrete."""
        ...

    @property
    def dropped(self) -> int:
        """Travaux abandonnes faute de place dans la file depuis le demarrage."""
        ...
