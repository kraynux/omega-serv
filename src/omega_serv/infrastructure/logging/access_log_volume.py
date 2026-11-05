"""Volume envoye par le serveur depuis son demarrage, lu dans l'access log (ecran Etat & Ressources,
2026-11-05) : Linux ne compte pas le reseau par processus et omega-serv n'a pas de compteur d'octets,
la somme des tailles de reponse (%b du format Combined, corps seulement, hors en-tetes) est la seule
mesure reelle disponible sans toucher au serveur.

Le journal peut etre enorme : le debut de la periode est trouve par dichotomie sur les horodatages
(quelques lectures), puis seule la suite est parcourue, par blocs ; les appels suivants reprennent a
l'offset rendu (seules les nouvelles lignes sont lues). Un fichier plus court que l'offset (rotation)
est relu depuis le debut de la periode."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from omega_serv.domain.logging.access_log_parser import parse_combined_log_line

_CHUNK = 1024 * 1024
_SEARCH_STOP = 64 * 1024
_PROBE_LINES = 20


def _timestamp_after(handle: BinaryIO, offset: int) -> datetime | None:
    """Horodatage de la premiere ligne lisible commencant apres `offset` (None si aucune)."""
    handle.seek(offset)
    if offset:
        handle.readline()  # ligne coupee par la position
    for _line_index in range(_PROBE_LINES):
        raw = handle.readline()
        if not raw:
            return None
        entry = parse_combined_log_line(raw.decode("utf-8", errors="replace"))
        if entry is not None:
            return entry.timestamp
    return None


def _start_offset(handle: BinaryIO, size: int, since: datetime) -> int:
    low, high = 0, size
    while high - low > _SEARCH_STOP:
        middle = (low + high) // 2
        stamp = _timestamp_after(handle, middle)
        if stamp is not None and stamp < since:
            low = middle
        else:
            high = middle
    return low


def sent_bytes_since(path: Path, since: datetime, offset: int | None = None) -> tuple[int, int]:
    """(octets de reponse des lignes horodatees >= `since` lues de `offset` a la fin, nouvel offset).
    `offset` None : premier appel, le debut de la periode est cherche. Fichier absent : (0, 0)."""
    try:
        size = os.stat(path).st_size
    except OSError:
        return 0, 0
    total = 0
    with open(path, "rb") as handle:
        if offset is None or offset > size:
            offset = _start_offset(handle, size, since)
        handle.seek(offset)
        pending = b""
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            lines = (pending + chunk).split(b"\n")
            pending = lines.pop()  # ligne pas encore terminee : relue au prochain appel
            for raw in lines:
                entry = parse_combined_log_line(raw.decode("utf-8", errors="replace"))
                if entry is not None and entry.timestamp >= since:
                    total += entry.response_size
        return total, handle.tell() - len(pending)
