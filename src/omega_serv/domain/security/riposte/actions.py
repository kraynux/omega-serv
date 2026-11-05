"""Actions RIPOSTE et commandes de l'interface (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.6-3.7, lot 4). Pur.

Une action est ENREGISTREE (`pending`) avant d'etre appliquee, puis `applied` ou `failed` ; elle finit
`expired` (echeance), `revoked` (levee : par l'utilisateur, une regle desactivee, l'arret d'urgence, ou
retiree hors RIPOSTE) ou reste `unknown` si la reconciliation ne peut pas conclure. Rien ne disparait :
une action terminee reste consultable (« voir, choisir, actionner », topo §6.7).

Toute action a une echeance (`ends_at`) : jamais de ban permanent pose par RIPOSTE.

Les details (`detail`) sont des CODES, traduits par l'interface (interfaces/cli/riposte_text.py)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ActionState = Literal["pending", "applied", "failed", "expired", "revoked", "unknown"]
IN_PROGRESS_STATES = frozenset({"pending", "applied", "unknown"})
FINISHED_STATES = frozenset({"failed", "expired", "revoked"})

FinishedBy = Literal["", "expiry", "user", "policy", "emergency", "outside"]

CommandKind = Literal[
    "revoke", "revoke_policy", "revoke_all", "not_recidive", "forget_source", "remove_exemption", "reload",
]
COMMAND_KINDS = frozenset({
    "revoke", "revoke_policy", "revoke_all", "not_recidive", "forget_source", "remove_exemption", "reload",
})
CommandState = Literal["pending", "done", "failed"]

EXEMPT_DURATIONS = {"24h": 24 * 3600, "7d": 7 * 24 * 3600, "forever": None}
"""Choix proposes par « Lever et exempter » (topo §6.7) ; `forever` = jusqu'a levee manuelle de l'exemption."""

MAX_FINISHED_ACTIONS = 100_000
MAX_COMMANDS = 10_000

_REASON_PREFIX = "riposte:"
_ACTION_ID = re.compile(r"^riposte:([0-9a-f]{12})(?:\s|$)")


@dataclass(frozen=True)
class RiposteAction:
    id: str
    ip: str
    kind: str
    """`local_ban`, `local_and_network_ban` ou `decoy` (RipostePolicy.action)."""
    policy_id: str
    created_at: datetime
    ends_at: datetime
    state: ActionState = "pending"
    tier_index: int | None = None
    decoy_profile: str | None = None
    subject_ids: tuple[str, ...] = ()
    """Leurre : identifiants Active Defense (IP + empreinte User-Agent) effectivement affectes."""
    detail: str = ""
    """Code : raison d'un echec, d'une levee, d'un etat inconnu."""
    finished_at: datetime | None = None
    finished_by: FinishedBy = ""
    counts_for_recidive: bool = True
    event_id: str = ""

    @property
    def in_progress(self) -> bool:
        return self.state in IN_PROGRESS_STATES

    @property
    def is_ban(self) -> bool:
        return self.kind in ("local_ban", "local_and_network_ban")

    @property
    def network(self) -> str:
        """Reseau ecrit dans la blocklist - meme forme que l'auto-ban du WAF (/128 en IPv6)."""
        return f"{self.ip}/128" if ":" in self.ip else f"{self.ip}/32"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "ip": self.ip, "kind": self.kind, "policy_id": self.policy_id,
            "created_at": self.created_at.isoformat(), "ends_at": self.ends_at.isoformat(), "state": self.state,
            "tier_index": self.tier_index, "decoy_profile": self.decoy_profile, "subject_ids": list(self.subject_ids),
            "detail": self.detail, "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "finished_by": self.finished_by, "counts_for_recidive": self.counts_for_recidive, "event_id": self.event_id,
        }


def blocklist_reason(action: RiposteAction) -> str:
    """Raison ecrite dans la blocklist. RELUE par le code (`action_id_from_reason`) : jamais traduite."""
    tier = f" #{action.tier_index + 1}" if action.tier_index is not None else ""
    return f"{_REASON_PREFIX}{action.id} {action.policy_id}{tier}"


def action_id_from_reason(reason: str) -> str | None:
    match = _ACTION_ID.match(reason)
    return match.group(1) if match else None


@dataclass(frozen=True)
class RiposteCommand:
    """Demande deposee par la TUI ou la CLI, executee par le processus (seul ecrivain du registre)."""
    id: int
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    state: CommandState = "pending"
    result: str = ""
    """Code de resultat (traduit par l'interface)."""
    result_params: dict[str, Any] = field(default_factory=dict)
    done_at: datetime | None = None


@dataclass(frozen=True)
class Exemption:
    """Exemption ajoutee par « Lever et exempter » : la source n'est plus jamais visee jusqu'a `until`
    (None = jusqu'a ce qu'on la retire). S'ajoute aux exemptions de la configuration."""
    network: str
    created_at: datetime
    until: datetime | None
    origin_action_id: str = ""

    def active(self, now: datetime) -> bool:
        return self.until is None or now < self.until
