"""Value objects Active Defense (plan_active_defense_omega_serv.md,
Phase 0) - evitent les chaines/dictionnaires non types dans le coeur
metier, meme convention que domain/security/waf/entities.py (Literal
plutot qu'Enum sauf besoin reel, comme Severity)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ThreatLevel = Literal["normal", "suspicious", "hostile", "contained"]

ActionType = Literal[
    "observe", "enrich_log", "delay", "rate_limit", "redirect_to_decoy", "create_incident", "export_ioc",
]

AttackClass = Literal[
    "scan", "credential_stuffing", "sqli", "xss", "path_traversal", "upload_probe", "api_probe", "unknown",
]

KNOWN_ATTACK_CLASSES: frozenset[str] = frozenset(
    {"scan", "credential_stuffing", "sqli", "xss", "path_traversal", "upload_probe", "api_probe", "unknown"}
)
"""Meme valeurs que le Literal AttackClass ci-dessus, dupliquees ici en
frozenset - necessaire pour valider une valeur lue depuis le JSON de
config (une simple str, jamais garantie par le typage statique) sans
recourir a un cast() non verifie (domain/security/active_defense/
config.py::validate_active_defense_config)."""

KNOWN_ACTION_TYPES: frozenset[str] = frozenset(
    {"observe", "enrich_log", "delay", "rate_limit", "redirect_to_decoy", "create_incident", "export_ioc"}
)
"""Meme valeurs que le Literal ActionType ci-dessus - meme raison que
KNOWN_ATTACK_CLASSES : valide `options.active_defense.war_mode.actions`
(Phase 4, DefensePlaybook) lu depuis le JSON de config."""

IsolationLevel = Literal["fixture", "proxy"]
"""Niveau 1 (fixture in-process, isolation faible assumee) vs Niveau 2
(proxy vers un backend reellement isole) - voir la section "Routage
vers les leurres" du plan."""

KNOWN_FIXTURE_PROFILE_NAMES: frozenset[str] = frozenset({"fake_admin", "fake_cms", "fake_api", "fake_secrets"})
"""Retour utilisateur (guide d'aide, Active Defense - Reglages) : le NOM
d'un profil `isolation_level == "fixture"` DOIT correspondre exactement
a une des 4 fixtures reellement implementees
(infrastructure/decoys/registry.py::FIXTURE_HANDLERS, domain ne peut
jamais importer infrastructure - meme duplication deliberee que
KNOWN_ATTACK_CLASSES vis-a-vis du Literal AttackClass, verifiee restee
synchronisee par test_active_defense_config.py) - piege reel trouve en
verifiant : un nom invalide n'etait detecte NULLE PART avant
validate_active_defense_config (InProcessFixtureDispatcher.render()
retourne silencieusement None, le fallback pass_through/reject
s'applique alors comme si aucun leurre n'existait, sans jamais avertir
que le profil est mal nomme)."""


@dataclass(frozen=True)
class ClientFingerprint:
    """Identifiant de correlation d'une source (plan §"Deception
    dynamique") - l'IP reste le premier identifiant operationnel en V1,
    le hash de User-Agent et le marqueur de session affinent la
    correlation sans jamais stocker l'User-Agent en clair dans les cles."""
    source_ip: str
    user_agent_hash: str
    session_marker: str | None = None

    @property
    def subject_id(self) -> str:
        return f"{self.source_ip}:{self.user_agent_hash}"


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


def clamp_confidence(value: int) -> int:
    """`Confidence` reste un simple `int` 0..100 (meme choix que le
    score WAF, jamais un type dedie pour une seule contrainte de
    bornes) - cette fonction est le seul endroit qui applique la
    contrainte, jamais une validation dupliquee ailleurs."""
    return max(0, min(100, value))
