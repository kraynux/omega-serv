"""Base du processus RIPOSTE, `var/lib/riposte.sqlite3` (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.8).
Separee de la base Active Defense (decision du topo §2.1 / etude §21-2) : RIPOSTE ne touche jamais
directement aux tables d'un autre module. Memes reglages que sqlite_active_defense_connection.py
(WAL, synchronous=NORMAL, erreurs sqlite3 traduites en OSError) ; schema versionne.

Lot 2 : positions de lecture, evenements vus, etat, audit. Lot 3 : historique des sources (JSON borne,
domain/security/riposte/history.py) et decisions. Lot 4 : actions, exemptions, commandes (CREATE TABLE IF
NOT EXISTS : ajout sans migration).

Droits : la base est creee par le processus RIPOSTE (compte du service) ; la CLI et la TUI de
l'utilisateur doivent pouvoir y deposer une commande -> base mise en 664 a la creation, comme les
journaux partages (FileLineLogger, 2026-10). Jamais une erreur si le chmod est refuse."""
from __future__ import annotations

import errno
import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS follower_positions (
    journal TEXT PRIMARY KEY,
    inode INTEGER NOT NULL,
    device INTEGER NOT NULL,
    offset INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    fingerprint_length INTEGER NOT NULL
);

-- Dedoublonnage : une ligne relue apres reecriture d'un journal n'est jamais comptee deux fois.
-- Purge par anciennete (seen_at), jamais une table qui grossit sans fin.
CREATE TABLE IF NOT EXISTS seen_events (
    event_id TEXT PRIMARY KEY,
    seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seen_events_seen_at ON seen_events(seen_at);

CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_occurred_at ON audit(occurred_at);

CREATE TABLE IF NOT EXISTS sources (
    ip TEXT PRIMARY KEY,
    history TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sources_updated_at ON sources(updated_at);

-- Seulement les decisions significatives (action decidee, refus des garde-fous, arret) : jamais une
-- ligne par attaque « sans suite », qu'un botnet multiplierait.
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decided_at TEXT NOT NULL,
    ip TEXT NOT NULL,
    event_id TEXT NOT NULL,
    status TEXT NOT NULL,
    policy_id TEXT,
    action TEXT,
    tier_index INTEGER,
    duration_seconds INTEGER,
    decoy_profile TEXT,
    reasons TEXT NOT NULL,
    applied INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_decisions_decided_at ON decisions(decided_at);
CREATE INDEX IF NOT EXISTS idx_decisions_ip ON decisions(ip, decided_at);

-- Registre des actions (lot 4) : une ligne par action, jamais supprimee tant qu'elle est en cours.
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    ip TEXT NOT NULL,
    kind TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    state TEXT NOT NULL,
    tier_index INTEGER,
    decoy_profile TEXT,
    subject_ids TEXT NOT NULL DEFAULT '[]',
    detail TEXT NOT NULL DEFAULT '',
    finished_at TEXT,
    finished_by TEXT NOT NULL DEFAULT '',
    counts_for_recidive INTEGER NOT NULL DEFAULT 1,
    event_id TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_actions_state ON actions(state, created_at);
CREATE INDEX IF NOT EXISTS idx_actions_ip ON actions(ip, created_at);

CREATE TABLE IF NOT EXISTS exemptions (
    network TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    until TEXT,
    origin_action_id TEXT NOT NULL DEFAULT ''
);

-- Commandes deposees par la TUI / la CLI, executees par le processus.
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    result TEXT NOT NULL DEFAULT '',
    result_params TEXT NOT NULL DEFAULT '{}',
    done_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_commands_state ON commands(state, id);
"""

_SHARED_MODE = 0o664


def open_riposte_connection(
    database_path: Path, *, read_only: bool = False, create: bool = True, lock_timeout: float = 1.0,
) -> sqlite3.Connection:
    """`read_only` : TUI / CLI (jamais d'ecriture, jamais de creation de fichier) ; le processus
    RIPOSTE est le seul ecrivain. Une base absente en lecture seule leve FileNotFoundError (« pas
    encore demarre » : message redige et traduit par l'appelant), jamais une base vide creee par
    erreur au mauvais endroit. `create=False` (depot d'une commande par la CLI / la TUI) : meme regle en
    ecriture - une base creee par l'utilisateur serait ensuite illisible en ecriture pour le service."""
    try:
        if read_only:
            if not database_path.exists():
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(database_path))
            connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        else:
            if not create and not database_path.exists():
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(database_path))
            database_path.parent.mkdir(parents=True, exist_ok=True)
            is_new = not database_path.exists()
            connection = sqlite3.connect(database_path)
            if is_new:
                _share(database_path)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(_SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),),
            )
            connection.commit()
        connection.execute(f"PRAGMA busy_timeout = {max(0, int(lock_timeout * 1000))}")
    except sqlite3.Error as exc:
        raise OSError(str(exc)) from exc
    return connection


def _share(database_path: Path) -> None:
    try:
        os.chmod(database_path, _SHARED_MODE)
    except OSError:
        pass
