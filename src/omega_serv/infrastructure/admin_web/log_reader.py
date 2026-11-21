"""Lecture des journaux pour le tableau de bord web, lot 4 (plan §5.2 : instantane et direct).

- `tail` : les N dernieres lignes, lecture bornee en octets depuis la fin (jamais un gros fichier lu en entier) ; rend
  aussi la taille du fichier, qui sert de point de depart au mode direct ;
- `read_from` : les lignes ajoutees depuis une position (en octets), seulement des lignes completes, bornees ; un
  fichier plus court que la position = rotation : reprise au debut, signalee.

Jamais de chemin venu du navigateur : l'appelant ne passe ici que les chemins de la bibliotheque de l'instance."""
from __future__ import annotations

import os
from pathlib import Path

MAX_TAIL_BYTES = 512 * 1024
MAX_READ_BYTES = 64 * 1024


def _decode(raw: bytes) -> list[str]:
    """Scan de securite n° 2 (2026-11-20, F29) : decoupe sur `\n` SEULEMENT, comme le fichier sur disque.
    splitlines() coupait aussi sur U+0085 (NEL), U+2028 et U+2029, qu'un client pouvait glisser dans son
    User-Agent : une fausse ligne apparaissait dans la visionneuse web."""
    lines = raw.decode("utf-8", errors="replace").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line.removesuffix("\r") for line in lines]


def tail(path: Path, max_lines: int) -> tuple[list[str], int]:
    with path.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        start = max(0, size - MAX_TAIL_BYTES)
        handle.seek(start)
        raw = handle.read(size - start)
    lines = _decode(raw)
    if start > 0 and lines:
        lines = lines[1:]  # premiere ligne coupee par la borne
    return lines[-max_lines:], size


def read_from(path: Path, cursor: int) -> tuple[list[str], int, bool]:
    """(nouvelles lignes, nouvelle position, rotation detectee)."""
    with path.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        rotated = size < cursor
        position = 0 if rotated else cursor
        handle.seek(position)
        raw = handle.read(min(MAX_READ_BYTES, size - position))
    end = raw.rfind(b"\n")
    if end < 0:
        return [], position, rotated  # pas encore de ligne complete
    return _decode(raw[:end]), position + end + 1, rotated
