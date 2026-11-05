"""Formatage pur du journal des evenements de securite (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md, lot 1) -
JSON Lines, `var/log/security-events.jsonl` par defaut.

Active Defense produisait deja ces evenements metier (domain/security/active_defense/events.py :
escalade de niveau, incident ouvert, leurre affecte) mais personne ne les consommait : le serveur
les jetait. Ce journal les rend visibles a un lecteur EXTERNE au processus serveur (RIPOSTE, plus
tard omega-jail ou tout autre outil), le seul moyen sur en mode boost (N workers, N processus : un
bus d'evenements en memoire n'existerait qu'une fois par worker).

Contrat machine (lu par des programmes, jamais traduit - D18) :
- une ligne JSON par evenement, `schema_version` en tete (1) ;
- `event_id` unique (dedoublonnage par le lecteur si le fichier est relu) ;
- `type` parmi SECURITY_EVENT_TYPES ; les champs absents (None) sont omis, jamais ecrits a null ;
- jamais de corps de requete, d'en-tetes ni de User-Agent en clair (deja dans le journal enrichi
  quand l'utilisateur l'a demande) : seulement l'IP, l'identifiant de source (IP + empreinte UA)
  et la qualification.
Une ligne par EVENEMENT (escalade, incident, affectation, visite de leurre), jamais par requete
normale : aucun cout sur le trafic legitime."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from omega_serv.domain.logging.access_log_format import sanitize_log_field
from omega_serv.domain.security.active_defense.value_objects import AttackClass, ThreatLevel

SECURITY_EVENTS_SCHEMA_VERSION = 1

SecurityEventType = Literal["threat_escalated", "incident_opened", "deception_assigned", "decoy_hit"]

SECURITY_EVENT_TYPES: frozenset[str] = frozenset(
    {"threat_escalated", "incident_opened", "deception_assigned", "decoy_hit"}
)
"""Memes valeurs que le Literal ci-dessus (validation d'une ligne relue par un lecteur)."""


@dataclass(frozen=True)
class SecurityEvent:
    event_id: str
    type: SecurityEventType
    timestamp: datetime
    subject_id: str
    remote_ip: str
    level: ThreatLevel | None = None
    previous_level: ThreatLevel | None = None
    score: int | None = None
    attack_class: AttackClass | None = None
    incident_id: str | None = None
    decoy_profile: str | None = None


def format_security_event_line(event: SecurityEvent) -> str:
    record: dict[str, object] = {
        "schema_version": SECURITY_EVENTS_SCHEMA_VERSION,
        "event_id": sanitize_log_field(event.event_id, 64),
        "type": event.type,
        "timestamp": event.timestamp.isoformat(),
        "subject_id": sanitize_log_field(event.subject_id, 128),
        "remote_ip": sanitize_log_field(event.remote_ip, 64),
    }
    optional: dict[str, object | None] = {
        "level": event.level,
        "previous_level": event.previous_level,
        "score": event.score,
        "attack_class": event.attack_class,
        "incident_id": sanitize_log_field(event.incident_id, 64) if event.incident_id is not None else None,
        "decoy_profile": sanitize_log_field(event.decoy_profile, 64) if event.decoy_profile is not None else None,
    }
    record.update({key: value for key, value in optional.items() if value is not None})
    return json.dumps(record, ensure_ascii=False)
