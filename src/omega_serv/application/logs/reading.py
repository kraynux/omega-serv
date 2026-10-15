"""Lecture + parsing generique partagee entre `top_ips.py` et le Viewer
Simple (gestion des logs, refonte menu 2026-10-15, porte depuis
omega-log) - un seul point de verite plutot que duplique.

Lecture INVERSEE avec arret anticipe pour toute requete a PERIODE
explicite (24h/7j/30j, jamais "Tout") : un fichier de log reel peut
compter des centaines de milliers de lignes sur plusieurs mois -
parser l'integralite du fichier avant de filtrer en memoire gaspillerait
l'essentiel du travail pour une fenetre de quelques jours. Lit le
fichier par blocs depuis la FIN (jamais charge en entier en memoire) et
s'arrete des qu'un nombre suffisant de lignes CONSECUTIVES plus vieilles
que la periode est rencontre - un fichier d'acces reel est pour
l'essentiel trie chronologiquement, cet arret anticipe couvre le cas
normal sans perte de lignes recentes. Seule la requete "Tout"
(period=None) doit encore tout lire - aucun moyen de l'eviter pour un
total exhaustif."""
from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from omega_serv.domain.logs.models import LogEntry
from omega_serv.domain.logs.parser import parse_log_line

PERIOD_TO_TIMEDELTA = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_REVERSE_CHUNK_SIZE = 262144  # 256 KiB
_MAX_CONSECUTIVE_OLD_LINES = 500
"""Marge de securite avant de considerer la fenetre vraiment depassee :
un fichier n'est pas forcement PARFAITEMENT trie chronologiquement
(ligne isolee en retard, tampon applicatif qui vide plusieurs sources) -
exige ce nombre de lignes CONSECUTIVES plus vieilles que la periode,
jamais une seule ligne isolee, avant d'arreter la lecture."""


def _iter_lines_reverse(path: str) -> Iterator[str]:
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        position = f.tell()
        trailing = b""
        while position > 0:
            read_size = min(_REVERSE_CHUNK_SIZE, position)
            position -= read_size
            f.seek(position)
            chunk = f.read(read_size) + trailing
            parts = chunk.split(b"\n")
            trailing = parts[0]  # premiere "ligne" du bloc : potentiellement incomplete
            for raw in reversed(parts[1:]):
                yield raw.decode("utf-8", errors="replace")
        if trailing:
            yield trailing.decode("utf-8", errors="replace")


def _read_entries_for_period(path: str, *, period: str, now: datetime) -> list[LogEntry]:
    cutoff = now - PERIOD_TO_TIMEDELTA[period]
    entries: list[LogEntry] = []
    consecutive_old = 0
    for raw_line in _iter_lines_reverse(path):
        entry = parse_log_line(raw_line, line_number=0, log_path=path)
        if entry is None:
            continue
        if entry.timestamp >= cutoff:
            entries.append(entry)
            consecutive_old = 0
        else:
            consecutive_old += 1
            if consecutive_old >= _MAX_CONSECUTIVE_OLD_LINES:
                break
    entries.reverse()
    return entries


def read_entries(path: str) -> list[LogEntry]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []

    entries: list[LogEntry] = []
    for line_number, line in enumerate(lines, start=1):
        entry = parse_log_line(line, line_number=line_number, log_path=path)
        if entry is not None:
            entries.append(entry)
    return entries


def read_entries_for_paths(
    paths: list[str], *, period: str | None = None, now: datetime | None = None,
) -> list[LogEntry]:
    now = now or datetime.now(timezone.utc)
    entries: list[LogEntry] = []

    for path in paths:
        if period is not None:
            try:
                entries.extend(_read_entries_for_period(path, period=period, now=now))
            except OSError:
                pass
            continue

        path_entries = read_entries(path)
        entries.extend(path_entries)

    return entries
