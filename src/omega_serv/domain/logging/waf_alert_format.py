"""Formatage pur des lignes d'alerte WAF (doc WAF §9, "waf_logging") -
JSON Lines, un enregistrement par requete inspectee ayant produit au
moins un finding. Aucune I/O ici (voir access_log_format.py, meme
patron) - l'ecriture reelle passe par LoggerPort.

Propriete de securite garantie par construction : `WafFinding` (domain/
security/waf/entities.py) ne transporte jamais de texte de requete
brut (payload, body, query complete) - seulement id de regle, pack,
severite, poids et scope. Impossible d'ecrire accidentellement un
secret/token/mot de passe dans une alerte via les findings, la seule
donnee "libre" journalisee est le chemin et le user-agent, tous deux
tronques ici (doc WAF, checklist "Informations dans les logs").

Cette garantie ne couvrait PAS `entry.body_excerpt` (retour utilisateur,
audit securite 2026-09-14) : un champ separe des findings, journalise
verbatim des que `include_body_excerpt` est actif - un `POST /login`
capture pour diagnostiquer une attaque exposait alors le mot de passe
soumis en clair dans l'alerte. `redact_form_urlencoded_body` rediged
desormais les valeurs sensibles AVANT troncature - avec sa liste de
CHAMPS DE FORMULAIRE par defaut (`DEFAULT_SENSITIVE_BODY_FIELDS`),
jamais `mask_headers` (qui liste des NOMS D'EN-TETE comme "cookie",
"password" n'y figure d'ailleurs pas - le reutiliser ici aurait laisse
passer exactement le cas signale)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from omega_serv.domain.logging.access_log_format import sanitize_log_field
from omega_serv.domain.logging.body_redaction import redact_form_urlencoded_body
from omega_serv.domain.security.waf.config import WafLoggingConfig
from omega_serv.domain.security.waf.entities import WafDecision


@dataclass(frozen=True)
class WafAlertEntry:
    request_id: str
    timestamp: datetime
    remote_ip: str
    method: str
    path: str
    user_agent: str | None
    decision: WafDecision
    duration_ms: float
    zone_id: str | None = None
    body_excerpt: str | None = None


def format_waf_alert_line(entry: WafAlertEntry, logging_config: WafLoggingConfig) -> str:
    body_excerpt = None
    if logging_config.include_body_excerpt and entry.body_excerpt:
        redacted_body = redact_form_urlencoded_body(entry.body_excerpt)
        body_excerpt = redacted_body[: logging_config.body_excerpt_max_bytes] or None

    record = {
        "timestamp": entry.timestamp.isoformat(),
        "request_id": sanitize_log_field(entry.request_id, 64),
        "remote_ip": sanitize_log_field(entry.remote_ip, 64),
        "method": sanitize_log_field(entry.method, 16),
        "path": sanitize_log_field(entry.path, logging_config.max_path_chars),
        "user_agent": sanitize_log_field(entry.user_agent, logging_config.max_user_agent_chars) if entry.user_agent else None,
        "action": entry.decision.action,
        "status_code": entry.decision.status_code,
        "score": entry.decision.score,
        "rules": [f.rule_id for f in entry.decision.findings],
        "log_level": entry.decision.log_level,
        "zone": entry.zone_id or "default",
        "duration_ms": round(entry.duration_ms, 3),
    }
    if body_excerpt is not None:
        record["body_excerpt"] = body_excerpt
    return json.dumps(record, ensure_ascii=False)
