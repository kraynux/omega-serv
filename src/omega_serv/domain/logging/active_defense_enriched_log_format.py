# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Formatage pur des lignes de journalisation enrichie Active Defense
(plan_active_defense_omega_serv.md, Phase 4, action "enrich_log") -
JSON Lines, un enregistrement par requete d'une source deja marquee
(niveau != normal). Aucune I/O ici (meme patron que waf_alert_format.py) -
l'ecriture reelle passe par LoggerPort, dans un fichier SEPARE du log
WAF/production (plan §"Journalisation et protection des donnees" :
"separer les logs de deception des logs de production").

Redaction systematique appliquee ICI, jamais laissee a l'appelant :
`redact_fields` (headers) et `capture_request_body`/`max_body_bytes`
(corps, tronque, jamais inclus si `capture_request_body` est faux -
seul un hash SHA-256 du corps est alors conserve, cf.
policies.py::hash_payload).

Retour utilisateur (audit securite, 2026-09-14) : le corps captur
etait journalise VERBATIM des que `capture_request_body` est actif -
ironique puisqu'Active Defense sert justement a detecter le credential
stuffing, un `POST /login` intercepte finissant alors en clair dans ce
meme journal. `redact_form_urlencoded_body` (reutilise la meme liste
`redact_fields` que les en-tetes) rediged desormais les valeurs
sensibles AVANT troncature - redigee avant de tronquer, jamais apres,
pour ne jamais risquer de laisser fuir la moitie d'une valeur
sensible coupee en cours de troncature."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from omega_serv.domain.logging.access_log_format import sanitize_log_field
from omega_serv.domain.logging.body_redaction import redact_form_urlencoded_body
from omega_serv.domain.security.active_defense.config import ActiveDefenseLoggingConfig
from omega_serv.domain.security.active_defense.policies import hash_payload, redact_fields
from omega_serv.domain.security.active_defense.value_objects import AttackClass, ThreatLevel


@dataclass(frozen=True)
class EnrichedLogEntry:
    timestamp: datetime
    subject_id: str
    remote_ip: str
    method: str
    path: str
    user_agent: str | None
    score: int
    level: ThreatLevel
    attack_class: AttackClass
    headers: dict[str, str]
    body: bytes | None = None


def format_enriched_log_line(entry: EnrichedLogEntry, logging_config: ActiveDefenseLoggingConfig) -> str:
    redacted_headers = redact_fields(entry.headers, logging_config.redact_fields)
    record: dict[str, object] = {
        "timestamp": entry.timestamp.isoformat(),
        "subject_id": sanitize_log_field(entry.subject_id, 128),
        "remote_ip": sanitize_log_field(entry.remote_ip, 64),
        "method": sanitize_log_field(entry.method, 16),
        "path": sanitize_log_field(entry.path, 512),
        "user_agent": sanitize_log_field(entry.user_agent, 256) if entry.user_agent else None,
        "score": entry.score,
        "level": entry.level,
        "attack_class": entry.attack_class,
        "headers": redacted_headers,
    }
    if entry.body:
        if logging_config.capture_request_body:
            decoded_body = entry.body.decode("utf-8", errors="replace")
            redacted_body = redact_form_urlencoded_body(decoded_body, logging_config.redact_fields)
            record["body_excerpt"] = redacted_body[: logging_config.max_body_bytes]
        else:
            record["body_sha256"] = hash_payload(entry.body)
    return json.dumps(record, ensure_ascii=False)
