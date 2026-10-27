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


RuleScope = Literal["path", "query", "body", "headers", "user_agent", "referer"]

_VALID_SCOPES: frozenset[str] = frozenset({"path", "query", "body", "headers", "user_agent", "referer"})


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
    # Motif d'exceptions (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md
    # §3.10-3) : un texte qui le matche ne declenche JAMAIS la regle,
    # meme s'il matche `pattern` - exception prioritaire. None = aucune
    # exception (comportement de toutes les regles existantes).
    exclude_pattern: str | None = None


@dataclass(frozen=True)
class RulePack:
    """Un fichier de regles charge (core.json, sensitive-paths.json...).
    `enabled=False` desactive tout le pack sans supprimer son contenu."""
    version: int
    pack: str
    enabled: bool
    rules: tuple[RuleDefinition, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KeywordListDefinition:
    """Reference a un fichier texte "un mot-cle par ligne" (OMEGA-SERV_
    PLAN-DETAILLE_REFERER_ET_MAGNET_WAF.md, lot B) - alternative plus
    legere qu'un `RulePack` JSON complet pour une liste qui s'allonge
    dans le temps (ex. mots-clefs de spam Referer). `file` est un chemin
    relatif au projet, jamais absolu (meme regle que les autres chemins
    de configuration). Converti en une regle unique a l'alternance par
    domain/security/waf/keyword_list.py - ne transporte ici que la
    reference, jamais le contenu du fichier (aucune I/O dans ce module).

    Champs ajoutes par OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md (tous
    avec un defaut = comportement anterieur strictement identique) :
    - `match` : "substring" (defaut, recherche de sous-chaine, ex. spam
      Referer) ou "path" (une ligne = un chemin, frontieres de segments
      respectees, jokers `/*.ext`, exceptions `!/x` - §3.1) ;
    - `anchor` : "any_segment" (l'entree peut suivre n'importe quel '/')
      ou "root" (debut du chemin) - n'a de sens qu'avec match="path" ;
    - `observe_only` : journalise sans compter ni dans le score ni dans
      la reputation (mode essai, §3.10-5) ;
    - `escalation_*` : recidive propre a la liste (§3.12) -
      `escalation_threshold` a 0 = pas de seuil propre (compteur commun
      `reputation.suspicious_threshold`), `auto_block_duration_seconds`
      a None = duree commune `reputation.auto_block_duration_seconds`."""
    id: str
    scope: tuple[str, ...]
    file: str
    weight: int = 1
    enabled: bool = True
    match: Literal["substring", "path"] = "substring"
    anchor: Literal["any_segment", "root"] = "any_segment"
    observe_only: bool = False
    escalation_threshold: int = 0
    escalation_window_seconds: int = 600
    auto_block_duration_seconds: int | None = None
    # Nom affiche dans l'ecran WAF Custom (assistant, lot 6) - purement descriptif.
    label: str = ""


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
    # Rejet de debit d'une source sure (OMEGA-SERV_ETUDE_RATE_LIMIT_EXCLUSIONS.md
    # D4) : la reponse reste un blocage (429), mais l'alerte est journalisee
    # avec l'action "throttle" pour que fail2ban ne la compte jamais.
    throttle_only: bool = False
    # Rejet de VOLUME renvoye par le script magnet (429/413/414, son propre
    # rate limit) : jamais une detection - aucun finding, donc jamais compte
    # par la reputation ni l'auto-ban (decision utilisateur 2026-10-26, cas
    # reel : une page de captures en 4G faisait bannir le visiteur).
    volume_only: bool = False


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
