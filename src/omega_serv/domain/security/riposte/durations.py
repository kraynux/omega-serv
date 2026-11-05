"""Durees saisies dans l'interface RIPOSTE (formulaire, reglages) : « 1h, 6h, 24h, 7d ». Les unites sont
des symboles, jamais traduits (s, m/min, h, d/j), pour qu'une valeur affichee puisse toujours etre relue,
dans toutes les langues. Un nombre seul = secondes. Pur : aucune I/O."""
from __future__ import annotations

import re

_UNITS = {"s": 1, "m": 60, "min": 60, "h": 3600, "d": 86400, "j": 86400}
_DURATION = re.compile(r"^\s*(\d+)\s*(s|min|m|h|d|j)?\s*$", re.IGNORECASE)


def parse_duration(text: str) -> int | None:
    """Secondes, ou None si la saisie n'est pas une duree."""
    match = _DURATION.match(text)
    if match is None:
        return None
    return int(match.group(1)) * _UNITS[(match.group(2) or "s").lower()]


def parse_durations(text: str) -> tuple[int, ...] | None:
    """Liste separee par des virgules ; None si un element est invalide (liste vide = ())."""
    parts = [part for part in text.split(",") if part.strip()]
    values = [parse_duration(part) for part in parts]
    if any(value is None for value in values):
        return None
    return tuple(value for value in values if value is not None)


def duration_text(seconds: int) -> str:
    """Forme relisible par `parse_duration` (jamais traduite) : la plus grande unite exacte."""
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds and seconds % size == 0:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def durations_text(values: tuple[int, ...]) -> str:
    return ", ".join(duration_text(value) for value in values)
