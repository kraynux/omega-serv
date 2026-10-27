"""Seul module autorise a importer `sqlite3` (plan_active_defense_omega_
serv.md, section "Persistance" - nouveau contrat import-linter,
pyproject.toml). Premier usage de stockage relationnel dans ce projet -
tout le reste (config, profils, registre d'instances, reglages,
blocklist WAF) est du JSON simple via FilesystemPort ; ce module reste
volontairement le seul point de contact avec `sqlite3`, les
repositories concrets (sqlite_threat_state_repository.py etc.)
recoivent une connexion deja ouverte."""
from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
-- Phase 2 : la table "threat_observations" independante (creee en
-- Phase 1, jamais peuplee) est retiree au profit de
-- "incident_observations", scopee a un incident - les observations
-- individuelles ne sont durables que lorsqu'elles font deja partie
-- d'une enquete reelle (score >= incident_score) ; en-dessous, seul
-- l'agregat threat_states.score compte, jamais un historique complet
-- pour un simple "suspicious" jamais escalade.
CREATE TABLE IF NOT EXISTS threat_states (
    subject_id TEXT PRIMARY KEY,
    score INTEGER NOT NULL,
    level TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    active_actions TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_threat_states_expires_at ON threat_states(expires_at);

CREATE TABLE IF NOT EXISTS active_defense_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_log_occurred_at ON active_defense_audit_log(occurred_at);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    status TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_incidents_subject_id ON incidents(subject_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);

CREATE TABLE IF NOT EXISTS incident_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_incident_events_incident_id ON incident_events(incident_id, occurred_at);

CREATE TABLE IF NOT EXISTS incident_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    attack_class TEXT NOT NULL,
    score_delta INTEGER NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_incident_observations_incident_id ON incident_observations(incident_id, observed_at);

CREATE TABLE IF NOT EXISTS incident_history_omissions (
    incident_id TEXT PRIMARY KEY,
    omitted_observations INTEGER NOT NULL DEFAULT 0,
    omitted_events INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS indicators (
    indicator_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    shareable INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_indicators_incident_id ON indicators(incident_id);

-- Phase 3 : affectation source -> profil de leurre. Une seule ligne par
-- subject_id (jamais deux profils simultanes pour la meme source, V1) -
-- l'expiration est verifiee cote domaine (is_assignment_active), jamais
-- cote SQL (une ligne expiree reste lisible pour l'audit/CLI, seule sa
-- validite en tant que decision de routage en depend).
CREATE TABLE IF NOT EXISTS deception_assignments (
    subject_id TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deception_assignments_expires_at ON deception_assignments(expires_at);
"""


def open_active_defense_connection(database_path: Path, lock_timeout: float | None = None) -> sqlite3.Connection:
    """Cree le repertoire parent si necessaire (meme convention que
    JsonInstanceRegistry - jamais suppose deja present), active le mode
    WAL (lectures concurrentes pendant une ecriture - la TUI/CLI peuvent
    consulter l'etat pendant qu'une requete HTTP l'ecrit), applique le
    schema (idempotent, CREATE TABLE/INDEX IF NOT EXISTS).

    Retour utilisateur 2026-09-13 (cas reel rencontre : `var/lib/`
    appartenant au compte systeme dedie omega-serv, session utilisateur
    n'ayant pas encore rafraichi son appartenance de groupe) : toute
    erreur `sqlite3.Error` est traduite en `OSError` - `sqlite3` reste
    confine a ce seul module (contrat import-linter), donc les
    appelants (CLI/TUI/serveur) ne peuvent attraper que des types
    standards, jamais `sqlite3.OperationalError` directement.

    `lock_timeout` : attente maximale d'un verrou APRES l'ouverture (5 s par defaut, celui de
    sqlite3, pour la CLI et la TUI ; l'ouverture et le schema gardent toujours 5 s). Le serveur
    passe une valeur courte (active_defense_write_behind.py) : une attente sur la boucle asyncio
    figeait tout le serveur (mesure du 2026-10-26)."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        # Reglage recommande par SQLite en mode WAL (decision utilisateur 2026-10-26,
        # OMEGA-SERV_ETUDE_PERFORMANCE.md priorite 4) : plus de synchronisation disque
        # a chaque transaction - mesure : 3,1-3,5 ms -> 0,3 ms par requete suspecte,
        # temps pendant lequel tout le serveur etait bloque. Jamais de corruption ; une
        # coupure de courant peut seulement perdre les toutes dernieres ecritures.
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.executescript(_SCHEMA)
        connection.commit()
        if lock_timeout is not None:
            connection.execute(f"PRAGMA busy_timeout = {max(0, int(lock_timeout * 1000))}")
    except sqlite3.Error as exc:
        raise OSError(str(exc)) from exc
    return connection
