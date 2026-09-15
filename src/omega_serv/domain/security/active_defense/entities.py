# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Entites Active Defense (plan_active_defense_omega_serv.md, Phase 0).
Domaine pur - aucune I/O, aucune dependance vers infrastructure/
interfaces. Reutilise directement WafDecision/BlocklistEntry de
domain/security/waf/entities.py (un domaine peut dependre d'un autre
domaine dans cette Clean Architecture - seule la dependance vers
l'exterieur, infrastructure/interfaces, est interdite)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from omega_serv.domain.security.active_defense.value_objects import (
    ActionType,
    AttackClass,
    IsolationLevel,
    ThreatLevel,
)


@dataclass(frozen=True)
class ThreatSubject:
    """Source observee - IP et attributs de correlation non sensibles
    ou minimises (plan §"Domaine metier"). `subject_id` est la cle
    stable utilisee par tous les repositories (voir ClientFingerprint.
    subject_id)."""
    subject_id: str
    source_ip: str
    user_agent_hash: str | None = None


@dataclass(frozen=True)
class ThreatObservation:
    """Fait observe, deja traduit depuis les decisions WAF existantes
    (jamais un recalcul de score independant - voir "Domaine metier"
    du plan)."""
    subject_id: str
    observed_at: datetime
    kind: Literal["waf_decision", "reputation_escalation", "blocklist_entry", "omega_fire_ban", "decoy_hit"]
    attack_class: AttackClass
    score_delta: int
    detail: str = ""
    """Description humaine courte - jamais un payload brut (meme regle
    que WafFinding, la redaction/troncature est geree separement)."""


@dataclass(frozen=True)
class ThreatState:
    """Etat courant d'une source (plan §"Domaine metier")."""
    subject_id: str
    score: int
    level: ThreatLevel
    updated_at: datetime
    expires_at: datetime
    active_actions: tuple[ActionType, ...] = ()


@dataclass(frozen=True)
class DeceptionProfile:
    """Leurre autorise - vient de la configuration (options.active_
    defense.settings.deception.profiles), jamais d'un repository
    persistant : comme WafConfig, un profil est une donnee de
    configuration statique, pas un etat mutable a l'execution."""
    name: str
    enabled: bool
    match_attack_classes: tuple[AttackClass, ...]
    isolation_level: IsolationLevel = "fixture"
    reverse_proxy_zone_name: str | None = None
    """Requis uniquement si isolation_level == "proxy" (Niveau 2) -
    voir "Routage vers les leurres" du plan."""


@dataclass(frozen=True)
class DeceptionAssignment:
    """Association temporaire source -> profil de leurre, seule partie
    de la deception qui est reellement un etat mutable persiste."""
    subject_id: str
    profile_name: str
    assigned_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class DefensePlaybook:
    """Ensemble versionne de declencheurs et actions autorisees (plan
    §"Mode guerre"). `scope` perd la valeur "global" de la version
    d'origine du document - voir "Configuration et activation"."""
    scope: Literal["source", "instance"]
    actions: tuple[ActionType, ...]
    suspicious_score: int = 30
    hostile_score: int = 60
    incident_score: int = 70


@dataclass(frozen=True)
class IncidentEvent:
    """Une entree de la timeline d'un incident - pas dans la liste
    d'origine du document mais necessaire pour GetIncidentTimelineQuery."""
    occurred_at: datetime
    kind: str
    detail: str


@dataclass(frozen=True)
class Incident:
    """Regroupe les observations correlees, les actions et les IoC
    d'une campagne (plan §"Domaine metier")."""
    incident_id: str
    subject_id: str
    status: Literal["open", "closed"]
    opened_at: datetime
    closed_at: datetime | None = None
    observations: tuple[ThreatObservation, ...] = field(default_factory=tuple)
    events: tuple[IncidentEvent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Indicator:
    """IoC qualifie, avec contexte, confiance, dates d'observation et
    politique de partage (plan §"Domaine metier")."""
    indicator_id: str
    incident_id: str
    kind: Literal["ip", "user_agent", "path", "payload_hash"]
    value: str
    confidence: int
    first_seen: datetime
    last_seen: datetime
    shareable: bool = True


@dataclass(frozen=True)
class IncidentFilters:
    """Filtres de ListIncidentsQuery - jamais un dict ouvert dans le
    coeur metier. Pas de champ `level` : le niveau de menace est un
    attribut de `ThreatState`, jamais d'`Incident` lui-meme - un filtre
    par niveau qui ne ferait rien silencieusement serait pire que son
    absence."""
    status: Literal["open", "closed"] | None = None
    since: datetime | None = None


@dataclass(frozen=True)
class ExportResult:
    """Retour des exporters IoC/rapport - chemin reel + metadonnees,
    jamais le contenu lui-meme (deja ecrit sur disque par l'exporter)."""
    path: Path
    export_format: Literal["json", "csv", "markdown"]
    bytes_written: int


RoutingDecisionKind = Literal["production", "decoy_fixture", "decoy_proxy", "reject", "delayed"]


@dataclass(frozen=True)
class RoutingDecision:
    """Decision de routage (plan §"Routage vers les leurres") - un seul
    dataclass a plusieurs champs optionnels selon `kind`, meme style que
    WafDecision plutot qu'une hierarchie de classes. Le coeur applicatif
    ne connait ni le socket ni le framework HTTP ; l'infrastructure
    traduit cette decision soit vers le dispatcher de fixtures
    (decoy_fixture), soit vers serve_proxy() existant (decoy_proxy)."""
    kind: RoutingDecisionKind
    deception_profile_name: str | None = None
    """Requis si kind == "decoy_fixture"."""
    reverse_proxy_zone_name: str | None = None
    """Requis si kind == "decoy_proxy"."""
    status_code: int | None = None
    """Requis si kind == "reject"."""
    reason: str | None = None
    delay_seconds: float | None = None
    """Requis si kind == "delayed"."""
    next_kind: RoutingDecisionKind | None = None
    """La decision a appliquer une fois le delai ecoule, si kind == "delayed"."""


@dataclass(frozen=True)
class PlaybookPreview:
    """Retour de PreviewPlaybookDecisionQuery (plan §"Queries proposees",
    Phase 4 "Ajouter simulation, dry-run et explication de la decision") -
    n'importe QUELLE ecriture n'est jamais faite pour produire ce
    resultat (aucun repository.save()/create() appele), seulement des
    lectures et des fonctions pures de policies.py. `explanation` est une
    liste de phrases courtes, dans l'ordre des regles evaluees - jamais
    un seul champ opaque "would_act: bool" sans pouvoir dire pourquoi."""
    subject_id: str
    previous_score: int
    previous_level: ThreatLevel
    projected_score: int
    projected_level: ThreatLevel
    would_escalate: bool
    would_create_incident: bool
    would_assign_deception: bool
    selected_decoy_profile: str | None
    would_enrich_log: bool
    would_delay: bool
    delay_range_ms: tuple[int, int] | None
    would_rate_limit: bool
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class FirewallEvent:
    """Evenement omega-fire normalise (plan §"Integration omega-fire") -
    aucune implementation reelle du port qui les produit tant
    qu'omega-fire n'expose rien (voir OmegaFireEventsPort)."""
    event_id: str
    timestamp: datetime
    event_type: Literal["ban_applied", "ban_released"]
    subject_ip: str
    jail: str
    duration_seconds: int
    reason: str
