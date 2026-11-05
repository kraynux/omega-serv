"""Lecture des journaux suivis par RIPOSTE en evenements normalises (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md
§3.2-3.3, §3.9, lot 2). Pur : une ligne de texte entre, un evenement (ou la raison du rejet) sort.

Deux sources :
- `waf-alerts.log` (WAF, JSON, une ligne par decision notable) ;
- `security-events.jsonl` (Active Defense, lot 1, schema_version 1).

Regles (plan §3.3, §3.9) :
- une ligne WAF avec `stage == "blocklist"` est un **refus d'une source deja bannie**, jamais une
  nouvelle attaque (kind `blocklist_hit` : sert seulement a mesurer l'efficacite) ;
- une ligne WAF avec un score nul (limite de debit, rejet de volume magnet) n'est pas une attaque
  (kind `rate_limited` / `ignored`) ;
- sinon, `attack` - la classe d'attaque vient de la MEME heuristique qu'Active Defense
  (policies.py::attack_class_for_packs), jamais d'une seconde table.
Une ligne illisible, trop longue ou d'un schema inconnu n'est jamais une exception : elle est
rejetee avec une raison (comptee par l'appelant, ecran Etat : « lignes ignorees »)."""
from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, cast

from omega_serv.domain.logging.security_event_format import (
    SECURITY_EVENT_TYPES,
    SECURITY_EVENTS_SCHEMA_VERSION,
)
from omega_serv.domain.security.active_defense.policies import attack_class_for_packs

ObservedKind = Literal[
    "attack", "blocklist_hit", "rate_limited",
    "threat_escalated", "incident_opened", "deception_assigned", "decoy_hit",
]
EventSource = Literal["waf", "security"]

MAX_LINE_CHARS = 64 * 1024
"""Une ligne plus longue est rejetee sans etre analysee (journal forge ou corrompu)."""


@dataclass(frozen=True)
class ObservedEvent:
    """Evenement normalise, independant du journal d'origine. `event_id` sert au dedoublonnage
    (une ligne relue apres reecriture du journal n'est jamais comptee deux fois)."""
    source: EventSource
    event_id: str
    kind: ObservedKind
    timestamp: datetime
    remote_ip: str
    subject_id: str | None = None
    score: int | None = None
    attack_class: str | None = None
    level: str | None = None
    rules: tuple[str, ...] = ()
    decoy_profile: str | None = None
    incident_id: str | None = None


@dataclass(frozen=True)
class ParseResult:
    event: ObservedEvent | None
    rejected_reason: str | None = None
    """Identifiant technique (jamais un texte d'interface) : `empty`, `too_long`, `not_json`,
    `bad_schema`, `bad_ip`, `bad_timestamp`, `unknown_type`."""


def _rejected(reason: str) -> ParseResult:
    return ParseResult(event=None, rejected_reason=reason)


def _load(line: str) -> dict[str, Any] | ParseResult:
    stripped = line.strip()
    if not stripped:
        return _rejected("empty")
    if len(stripped) > MAX_LINE_CHARS:
        return _rejected("too_long")
    try:
        record = json.loads(stripped)
    except ValueError:
        return _rejected("not_json")
    if not isinstance(record, dict):
        return _rejected("bad_schema")
    return record


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _valid_ip(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def parse_waf_alert_line(line: str) -> ParseResult:
    loaded = _load(line)
    if isinstance(loaded, ParseResult):
        return loaded
    record = loaded
    request_id = record.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return _rejected("bad_schema")
    remote_ip = _valid_ip(record.get("remote_ip"))
    if remote_ip is None:
        return _rejected("bad_ip")
    timestamp = _timestamp(record.get("timestamp"))
    if timestamp is None:
        return _rejected("bad_timestamp")
    score = record.get("score")
    if not isinstance(score, int) or isinstance(score, bool):
        return _rejected("bad_schema")
    findings = record.get("findings") or []
    packs = tuple(f.get("pack", "") for f in findings if isinstance(f, dict))
    rules = tuple(str(r) for r in (record.get("rules") or []) if isinstance(r, str))
    stage = record.get("stage", "inspection")
    kind: ObservedKind
    if stage == "blocklist":
        kind = "blocklist_hit"
    elif stage == "rate_limit" or score <= 0:
        kind = "rate_limited"
    else:
        kind = "attack"
    return ParseResult(ObservedEvent(
        source="waf", event_id=f"waf:{request_id}", kind=kind, timestamp=timestamp, remote_ip=remote_ip,
        score=score, attack_class=attack_class_for_packs(packs) if kind == "attack" else None, rules=rules,
    ))


def parse_security_event_line(line: str) -> ParseResult:
    loaded = _load(line)
    if isinstance(loaded, ParseResult):
        return loaded
    record = loaded
    if record.get("schema_version") != SECURITY_EVENTS_SCHEMA_VERSION:
        return _rejected("bad_schema")
    event_type = record.get("type")
    if event_type not in SECURITY_EVENT_TYPES:
        return _rejected("unknown_type")
    event_id = record.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        return _rejected("bad_schema")
    remote_ip = _valid_ip(record.get("remote_ip"))
    if remote_ip is None:
        return _rejected("bad_ip")
    timestamp = _timestamp(record.get("timestamp"))
    if timestamp is None:
        return _rejected("bad_timestamp")
    subject_id = record.get("subject_id")
    score = record.get("score")

    def optional_str(key: str) -> str | None:
        value = record.get(key)
        return value if isinstance(value, str) else None

    return ParseResult(ObservedEvent(
        source="security", event_id=f"security:{event_id}", kind=cast(ObservedKind, event_type), timestamp=timestamp,
        remote_ip=remote_ip, subject_id=subject_id if isinstance(subject_id, str) else None,
        score=score if isinstance(score, int) and not isinstance(score, bool) else None,
        attack_class=optional_str("attack_class"), level=optional_str("level"),
        decoy_profile=optional_str("decoy_profile"), incident_id=optional_str("incident_id"),
    ))
