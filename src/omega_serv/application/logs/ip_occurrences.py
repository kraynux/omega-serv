"""Recherche manuelle d'une IP (« Voir et traiter IP », demande utilisateur 2026-11-07) : au lieu de calculer
le top et d'esperer y trouver l'adresse, on la saisit et on compte ses lignes dans chaque log selectionne,
fichier entier. Meme regle que le retrait (`domain/logs/ip_match.py`) : le compte affiche est exactement ce
que « Retirer cette IP » retirera."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.ip_match import ip_line_pattern, line_contains_ip


@dataclass(frozen=True)
class IpOccurrences:
    path: str
    count: int


def count_ip_occurrences(ip: str, paths: list[str]) -> list[IpOccurrences]:
    """Lecture en flux (un gros log n'est jamais charge en entier). Fichier absent : 0. Illisible par
    votre compte : LogPermissionError (le retrait serait de toute facon impossible)."""
    pattern = ip_line_pattern(ip)
    results: list[IpOccurrences] = []
    for path in paths:
        count = 0
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line_contains_ip(line, ip, pattern):
                        count += 1
        except FileNotFoundError:
            pass
        except PermissionError as exc:
            raise LogPermissionError(path) from exc
        results.append(IpOccurrences(path, count))
    return results
