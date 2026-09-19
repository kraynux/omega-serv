"""Entites du module WAF (OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md,
"Repartition Clean Architecture" : domain/security/ porte WafDecision,
WafFinding, severites, regles de decision et politiques de score -
jamais de logique reseau/filesystem ici."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RuleScope = Literal["path", "query", "body", "headers", "user_agent"]

_VALID_SCOPES: frozenset[str] = frozenset({"path", "query", "body", "headers", "user_agent"})


@dataclass(frozen=True)
class RuleDefinition:
    """Une regle de signature individuelle (doc WAF, "Format de regles
    generique"). `pattern` est une regex Python brute, compilee au
    chargement (jamais a chaque requete) - voir signature_engine.py."""
    id: str
    description: str
    scope: tuple[str, ...]
    pattern: str
    case_insensitive: bool = True
    weight: int = 1
    action: Literal["score"] = "score"
    enabled: bool = True


@dataclass(frozen=True)
class RulePack:
    """Un fichier de regles charge (core.json, sensitive-paths.json...).
    `enabled=False` desactive tout le pack sans supprimer son contenu."""
    version: int
    pack: str
    enabled: bool
    rules: tuple[RuleDefinition, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WafFinding:
    """Une regle declenchee pour une requete donnee (doc WAF §10 :
    jamais de payload brut stocke ici, seulement l'identifiant et le
    poids - le masquage des logs est une responsabilite separee,
    infrastructure/logging/waf_alert_logger.py)."""
    rule_id: str
    pack: str
    description: str
    severity: Severity
    weight: int
    scope: str


WafActionLiteral = Literal["allow", "log", "block"]


@dataclass(frozen=True)
class WafDecision:
    """Decision finale du moteur WAF pour une requete (doc WAF §10,
    forme fixee). Le moteur ne rend jamais de page HTML ni ne touche au
    socket - seul le serveur traduit cette decision en reponse HTTP."""
    action: WafActionLiteral
    status_code: int | None
    score: int
    findings: tuple[WafFinding, ...] = field(default_factory=tuple)
    log_level: str = "info"
    retry_after_seconds: int | None = None
    matched_zone_id: str | None = None
    blocked_reason: str | None = None


@dataclass(frozen=True)
class RateLimitPolicy:
    key: str = "client_ip"
    requests: int = 60
    window_seconds: int = 60
    response_status: int = 429


@dataclass(frozen=True)
class BlocklistEntry:
    """Une entree de blocklist (doc WAF §5) - `network` est une chaine
    CIDR ('203.0.113.25/32' ou un /32 implicite pour une IP seule).
    `expires_at` a None signifie un bannissement permanent (uniquement
    cree explicitement en CLI, jamais par l'auto-block, voir §8/checklist
    "Desactiver l'auto-block permanent par defaut")."""
    network: str
    reason: str
    created_at: str
    expires_at: str | None = None
    source: Literal["manual", "auto"] = "manual"
