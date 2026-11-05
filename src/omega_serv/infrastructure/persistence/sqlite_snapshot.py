"""Copie COHERENTE d'une base SQLite en service (sauvegarde de configuration, 2026-11-01).

Les bases Active Defense et RIPOSTE sont en mode WAL : archiver le fichier tel quel oublie les ecritures
encore dans `-wal`, et une copie faite pendant une ecriture peut etre incoherente. L'API de sauvegarde de
SQLite (`Connection.backup`) produit une copie complete et coherente pendant que le serveur ecrit - c'est
ce qui permet de sauvegarder sans jamais arreter le service. La base source est ouverte en LECTURE SEULE."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def snapshot_database(source: Path, destination: Path) -> None:
    """Leve OSError (jamais sqlite3.Error : contrat import-linter, sqlite3 reste confine ici)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_connection:
            source_connection.execute("PRAGMA busy_timeout = 5000")
            target = sqlite3.connect(destination)
            try:
                source_connection.backup(target)
            finally:
                target.close()
    except sqlite3.Error as exc:
        raise OSError(str(exc)) from exc
