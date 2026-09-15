# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Politiques Active Defense (plan_active_defense_omega_serv.md, Phase
0) - fonctions pures et deterministes, aucune I/O. Consomment les
decisions WAF DEJA calculees (WafDecision/ReputationDecision/
BlocklistEntry) comme signaux d'entree, ne recalculent jamais un score
independant a partir d'une requete brute - voir "Domaine metier" du
plan pour le raisonnement complet (evite une duplication avec
domain/security/waf/scoring.py et reputation.py)."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from omega_serv.domain.security.active_defense.config import WarModeConfig
from omega_serv.domain.security.active_defense.entities import (
    DeceptionAssignment,
    DeceptionProfile,
    DefensePlaybook,
    Incident,
    Indicator,
    ThreatObservation,
)
from omega_serv.domain.security.active_defense.value_objects import (
    ActionType,
    AttackClass,
    ThreatLevel,
    clamp_confidence,
)
from omega_serv.domain.security.waf.entities import WafDecision
from omega_serv.domain.security.waf.reputation import ReputationDecision

DEFAULT_REDACT_FIELDS: tuple[str, ...] = ("password", "token", "authorization", "cookie")

# Association pack WAF -> classe d'attaque (plan §"Honeypots V1"/"IoC et
# rapports" - heuristique simple par mot-cle, basee sur les noms de packs
# REELS deja livres par le WAF, jamais inventee : "body-sqli", "body-xss",
# "sensitive-paths", "scanner-ua" (voir domain/security/waf/, rounds
# WAF anterieurs). Premiere entree qui matche l'emporte.
_ATTACK_CLASS_BY_PACK_KEYWORD: tuple[tuple[str, AttackClass], ...] = (
    ("sqli", "sqli"),
    ("xss", "xss"),
    ("traversal", "path_traversal"),
    ("upload", "upload_probe"),
    ("scanner", "scan"),
    ("sensitive-paths", "scan"),
    ("credential", "credential_stuffing"),
)

_LEVEL_RANK: dict[ThreatLevel, int] = {"normal": 0, "suspicious": 1, "hostile": 2, "contained": 3}

# Poids de traduction observation -> delta de score (plan §"Domaine
# metier" - seul calcul propre a Active Defense, jamais un recalcul du
# score WAF lui-meme).
WAF_FINDING_SCORE_DELTA = 10
REPUTATION_ESCALATION_SCORE_DELTA = 25
BLOCKLIST_ENTRY_SCORE_DELTA = 25
OMEGA_FIRE_BAN_SCORE_DELTA = 25
DECOY_POST_SCORE_DELTA = 30


def score_delta_for_waf_decision(decision: WafDecision) -> int:
    """`decision.score > 0`, jamais `decision.action == "block"`
    specifiquement - le mode `log-only` du WAF (jamais bloquant par
    conception, cf. domain/security/waf/scoring.py) reste un signal
    reel pour Active Defense : c'est justement le deploiement le plus
    prudent et le plus courant, ne jamais le traiter comme s'il
    n'avait rien detecte."""
    return WAF_FINDING_SCORE_DELTA if decision.score > 0 else 0


def score_delta_for_reputation_escalation(decision: ReputationDecision) -> int:
    return REPUTATION_ESCALATION_SCORE_DELTA if decision.should_escalate else 0


def attack_class_for_waf_decision(decision: WafDecision) -> AttackClass:
    """Heuristique par mot-cle sur le nom du pack WAF declenche - jamais
    une verite absolue, seulement une premiere classification utile pour
    la selection de leurre et les IoC (plan §"Honeypots V1"). Retourne
    "unknown" si aucun mot-cle connu ne correspond (jamais une exception :
    une classification manquante ne doit jamais bloquer l'observation
    elle-meme)."""
    for finding in decision.findings:
        pack_lower = finding.pack.lower()
        for keyword, attack_class in _ATTACK_CLASS_BY_PACK_KEYWORD:
            if keyword in pack_lower:
                return attack_class
    return "unknown"


def build_observation_from_waf_decision(subject_id: str, decision: WafDecision, now: datetime) -> ThreatObservation:
    """Traduit une WafDecision deja calculee en ThreatObservation
    (plan §"Domaine metier") - jamais un recalcul de score, seulement
    une mise en forme. `detail` reste une description courte (regles
    declenchees, jamais un payload brut - meme regle que WafFinding)."""
    rule_ids = ",".join(f.rule_id for f in decision.findings) or "-"
    return ThreatObservation(
        subject_id=subject_id,
        observed_at=now,
        kind="waf_decision",
        attack_class=attack_class_for_waf_decision(decision),
        score_delta=score_delta_for_waf_decision(decision),
        detail=f"WAF {decision.action} (score={decision.score}, regles={rule_ids})",
    )


def level_rank(level: ThreatLevel) -> int:
    return _LEVEL_RANK[level]


def qualify_threat_level(
    score: int, *, suspicious_score: int, hostile_score: int, contained_score: int, known_ban: bool,
) -> ThreatLevel:
    """Traduit un score en ThreatLevel (plan §"Domaine metier" -
    exemple de logique metier). `contained` exige a la fois un score
    tres eleve ET un bannissement deja connu (WAF ou omega-fire) -
    jamais uniquement le score seul, pour ne jamais affirmer un
    confinement qui ne s'est pas reellement produit."""
    if score >= contained_score and known_ban:
        return "contained"
    if score >= hostile_score:
        return "hostile"
    if score >= suspicious_score:
        return "suspicious"
    return "normal"


def decay_score(score: int, elapsed_seconds: float, *, decay_amount: int, decay_interval_seconds: int) -> int:
    """Decroissance temporelle (plan : "-5 toutes les 15 minutes sans
    nouvel evenement"). `decay_interval_seconds` <= 0 desactive la
    decroissance (jamais une division par zero)."""
    if decay_interval_seconds <= 0 or elapsed_seconds <= 0:
        return score
    intervals = int(elapsed_seconds // decay_interval_seconds)
    return max(0, score - intervals * decay_amount)


def apply_observation(
    *,
    current_score: int,
    last_updated_at: datetime,
    now: datetime,
    score_delta: int,
    suspicious_score: int,
    hostile_score: int,
    contained_score: int,
    known_ban: bool,
    decay_amount: int = 5,
    decay_interval_seconds: int = 900,
) -> tuple[int, ThreatLevel]:
    """Combine decroissance + nouvelle observation en un seul point
    d'entree - jamais applique separement par un appelant (l'ordre
    decroissance-puis-ajout est une regle metier, pas un detail
    d'implementation laisse a l'appelant)."""
    elapsed_seconds = max(0.0, (now - last_updated_at).total_seconds())
    decayed_score = decay_score(
        current_score, elapsed_seconds, decay_amount=decay_amount, decay_interval_seconds=decay_interval_seconds,
    )
    new_score = max(0, decayed_score + score_delta)
    level = qualify_threat_level(
        new_score, suspicious_score=suspicious_score, hostile_score=hostile_score,
        contained_score=contained_score, known_ban=known_ban,
    )
    return new_score, level


def select_decoy_profile(
    attack_class: AttackClass, profiles: tuple[DeceptionProfile, ...],
) -> DeceptionProfile | None:
    """Selection deterministe : premier profil active dont
    `match_attack_classes` couvre la classe d'attaque observee, dans
    l'ordre fourni (celui de la configuration - jamais un ordre
    aleatoire ou base sur un tri implicite du dict)."""
    for profile in profiles:
        if profile.enabled and attack_class in profile.match_attack_classes:
            return profile
    return None


def is_assignment_active(assignment: DeceptionAssignment, now: datetime) -> bool:
    """Une affectation expiree ne doit jamais etre traitee comme active -
    jamais un TTL verifie a moitie (plan §"Deception dynamique",
    `assignments_ttl_seconds`)."""
    return now < assignment.expires_at


def decide_incident_transition(existing_open_incident: Incident | None, score: int, *, incident_score_threshold: int) -> str:
    """Retourne "open_new", "merge_into_existing" ou "no_change" (plan
    §"Cas d'usage applicatifs", CreateOrUpdateIncidentCommand). Base sur
    le SCORE brut et `WarModeThresholds.incident_score` (Phase 2,
    correction faite en implementant) - jamais sur `ThreatLevel`, qui a
    sa propre echelle independante (`suspicious_score`/`hostile_score`/
    `contained_score`) : les deux notions ne coincident pas forcement
    (§"Configuration et activation" - incident_score=70 se situe entre
    hostile_score=60 et contained_score=80 dans l'exemple du plan)."""
    if score < incident_score_threshold:
        return "no_change"
    return "merge_into_existing" if existing_open_incident is not None else "open_new"


def decide_incident_closure(level: ThreatLevel, quiet_seconds: float, *, close_after_quiet_seconds: int) -> bool:
    """Un incident ne se ferme jamais tant que la source n'est pas
    revenue a `normal` ET restee silencieuse assez longtemps - jamais
    une fermeture sur seul ecoulement de temps si le niveau reste eleve."""
    return level == "normal" and quiet_seconds >= close_after_quiet_seconds


def redact_fields(data: dict[str, str], fields_to_redact: tuple[str, ...] = DEFAULT_REDACT_FIELDS) -> dict[str, str]:
    """Reduction/anonymisation avant export ou journalisation enrichie
    (plan §"Journalisation et protection des donnees") - comparaison
    insensible a la casse, meme convention que WafLoggingConfig.mask_headers."""
    lowered_targets = {field.lower() for field in fields_to_redact}
    return {
        key: ("***REDACTED***" if key.lower() in lowered_targets else value)
        for key, value in data.items()
    }


def hash_payload(payload: bytes) -> str:
    """Empreinte cryptographique d'un payload (plan : "conserver une
    empreinte cryptographique du payload lorsque le contenu brut n'est
    pas indispensable") - SHA-256, meme algorithme que le reste du
    projet (comparaison de cle publique TLS, hachage de mot de passe
    scrypt utilise un sel distinct mais le meme choix d'algorithme
    stdlib partout)."""
    return hashlib.sha256(payload).hexdigest()


def validate_playbook_action(action: ActionType, playbook: DefensePlaybook) -> bool:
    """Verifie la compatibilite entre une action et le playbook
    applique (plan §"Politiques" - "validation de compatibilite entre
    une action et le profil applique")."""
    return action in playbook.actions


def build_playbook(war_mode: WarModeConfig) -> DefensePlaybook:
    """Traduit `WarModeConfig` (config JSON deja validee - `actions` est
    garanti n'contenir que des `ActionType` connus par
    `validate_active_defense_config`, jamais invoque sur une config non
    validee) en `DefensePlaybook` (plan §"Mode guerre", Phase 4). Simple
    mise en forme, aucun calcul - le cast() est sans risque pour la meme
    raison que `profiles_from_config` dans manage_deception.py."""
    return DefensePlaybook(
        scope=war_mode.scope,
        actions=cast("tuple[ActionType, ...]", war_mode.actions),
        suspicious_score=war_mode.thresholds.suspicious_score,
        hostile_score=war_mode.thresholds.hostile_score,
        incident_score=war_mode.thresholds.incident_score,
    )


def is_source_marked(level: ThreatLevel) -> bool:
    """Une source "marquee" (plan §"Mode guerre" : "ajouter un
    ralentissement borne, uniquement pour les sources marquees") est
    toute source qui n'est plus `normal` - meme definition reutilisee
    pour l'action `enrich_log` ("activer une journalisation enrichie"
    est cite au meme titre que le ralentissement dans "Deception
    dynamique"/"Mode guerre"), jamais une source encore `normal`."""
    return level != "normal"


def compute_slowdown_delay_ms(jitter_fraction: float, *, minimum_ms: int, maximum_ms: int, jitter_ms: int) -> int:
    """Delai borne et jitte (plan §"Mode guerre"/"Configuration et
    activation", `SlowdownConfig`) - fonction pure, `jitter_fraction`
    (0.0..1.0) est injecte par l'appelant (infrastructure, `random.random()`)
    plutot qu'appele ici, meme regle que `extract_indicators`/`id_factory` :
    aucune source d'alea dans le domaine. Base = `minimum_ms`, jusqu'a
    `jitter_ms` de bruit ajoute, jamais au-dela de `maximum_ms`."""
    jitter_fraction = max(0.0, min(1.0, jitter_fraction))
    return min(maximum_ms, minimum_ms + round(jitter_fraction * jitter_ms))


IndicatorKind = Literal["ip", "user_agent", "path", "payload_hash"]


@dataclass(frozen=True)
class IndicatorCandidate:
    """IoC sans identifiant - l'attribution d'un `indicator_id` est une
    operation impure (UUID aleatoire) deliberement laissee hors du
    domaine (meme regle que `request_id` dans infrastructure/server/
    asyncio_server.py, jamais genere en domain/) - voir `extract_indicators`."""
    kind: IndicatorKind
    value: str
    confidence: int
    first_seen: datetime
    last_seen: datetime


def extract_indicator_candidates(incident: Incident) -> list[IndicatorCandidate]:
    """Extrait les IoC directement disponibles a partir des observations
    d'un incident (plan §"IoC et rapports"). MVP honnete : seuls IP et
    User-Agent (haches) sont extraits en Phase 2 - `path`/`payload_hash`
    resteraient possibles avec des `ThreatObservation` plus riches
    (chemin cible, empreinte de payload), pas encore captures a ce
    stade, delibere et documente plutot que fait a moitie."""
    if not incident.observations:
        return []
    source_ip, _, user_agent_hash = incident.subject_id.partition(":")
    first_seen = min(o.observed_at for o in incident.observations)
    last_seen = max(o.observed_at for o in incident.observations)
    # Confiance proportionnelle au score cumule des observations - pas
    # une moyenne (une seule observation tres grave doit deja qualifier
    # l'IoC), plafonnee a 100 par clamp_confidence.
    confidence = clamp_confidence(sum(o.score_delta for o in incident.observations))
    candidates = [IndicatorCandidate(kind="ip", value=source_ip, confidence=confidence, first_seen=first_seen, last_seen=last_seen)]
    if user_agent_hash:
        candidates.append(
            IndicatorCandidate(
                kind="user_agent", value=user_agent_hash, confidence=confidence,
                first_seen=first_seen, last_seen=last_seen,
            )
        )
    return candidates


def extract_indicators(incident: Incident, id_factory: Callable[[], str]) -> list[Indicator]:
    """Assemble les `Indicator` complets - `id_factory` est injecte par
    l'appelant (infrastructure/exporters/, ou un test avec un generateur
    deterministe) plutot qu'un `uuid.uuid4()` appele directement ici,
    pour garder cette fonction testable de facon deterministe."""
    return [
        Indicator(
            indicator_id=id_factory(), incident_id=incident.incident_id, kind=c.kind, value=c.value,
            confidence=c.confidence, first_seen=c.first_seen, last_seen=c.last_seen, shareable=True,
        )
        for c in extract_indicator_candidates(incident)
    ]
