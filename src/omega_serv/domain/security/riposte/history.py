"""Memoire de recidive d'une source (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.3, lot 3). Pur.

Definitions (affichees telles quelles dans l'aide et dans « Simuler ») :
- **source** : une adresse IP (deja resolue derriere le proxy de confiance par le serveur) ;
- **activite** : une attaque vue par le WAF (score > 0, hors blocklist) ou une visite de leurre ;
- **episode** : une suite d'activites de la source sans silence de plus de `episode_gap` (1 h par defaut) ;
  un episode se termine aussi quand une action RIPOSTE commence (la suite, une fois l'action finie,
  est un nouvel episode) ;
- **retour** : un nouvel episode ;
- **palier** : rang de la prochaine action = nombre d'actions RIPOSTE deja prises contre la source dans
  la fenetre de recidive (30 j par defaut), plafonne au dernier palier - 30 j sans action = palier 1.
Les niveaux Active Defense (escalades) enrichissent l'episode en cours sans en creer.

Bornes : au plus MAX_EPISODES episodes et MAX_ACTIONS actions gardes par source (les plus recents) ;
`forget_before` retire tout ce qui est plus ancien que la retention (90 j)."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from omega_serv.domain.security.riposte.events import ObservedEvent

MAX_EPISODES = 50
MAX_ACTIONS = 50
LEVEL_RANK = {"normal": 0, "suspicious": 1, "hostile": 2, "contained": 3}


@dataclass(frozen=True)
class Episode:
    started_at: datetime
    last_seen_at: datetime
    attacks: int = 0
    attack_classes: tuple[str, ...] = ()
    max_level: str | None = None
    decoy_hits: int = 0
    blocklist_hits: int = 0
    """Refus d'une source deja bannie pendant l'episode (efficacite, jamais une activite)."""
    action_taken: bool = False
    """Une action RIPOSTE a deja ete decidee pendant cet episode (une seule par episode, plan §3.9)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(), "last_seen_at": self.last_seen_at.isoformat(),
            "attacks": self.attacks, "attack_classes": list(self.attack_classes), "max_level": self.max_level,
            "decoy_hits": self.decoy_hits, "blocklist_hits": self.blocklist_hits, "action_taken": self.action_taken,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Episode:
        return cls(
            started_at=datetime.fromisoformat(data["started_at"]),
            last_seen_at=datetime.fromisoformat(data["last_seen_at"]),
            attacks=int(data.get("attacks", 0)), attack_classes=tuple(data.get("attack_classes", ())),
            max_level=data.get("max_level"), decoy_hits=int(data.get("decoy_hits", 0)),
            blocklist_hits=int(data.get("blocklist_hits", 0)), action_taken=bool(data.get("action_taken", False)),
        )


@dataclass(frozen=True)
class PastAction:
    """Action RIPOSTE prise contre la source (sert au calcul du palier)."""
    taken_at: datetime
    ends_at: datetime
    policy_id: str
    tier_index: int
    counts_for_recidive: bool = True
    """Faux apres « Lever » avec « ne pas compter ce ban dans la recidive » (faux positif, topo §6.7)."""
    action_id: str = ""
    """Identifiant dans le registre des actions (lot 4) - vide pour une action simulee."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "taken_at": self.taken_at.isoformat(), "ends_at": self.ends_at.isoformat(), "policy_id": self.policy_id,
            "tier_index": self.tier_index, "counts_for_recidive": self.counts_for_recidive,
            "action_id": self.action_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PastAction:
        return cls(
            taken_at=datetime.fromisoformat(data["taken_at"]), ends_at=datetime.fromisoformat(data["ends_at"]),
            policy_id=str(data["policy_id"]), tier_index=int(data["tier_index"]),
            counts_for_recidive=bool(data.get("counts_for_recidive", True)),
            action_id=str(data.get("action_id", "")),
        )


@dataclass(frozen=True)
class SourceHistory:
    ip: str
    episodes: tuple[Episode, ...] = field(default_factory=tuple)
    actions: tuple[PastAction, ...] = field(default_factory=tuple)
    subject_ids: tuple[str, ...] = ()
    """Identifiants Active Defense (IP + empreinte User-Agent) vus pour cette IP - utiles pour les leurres.
    Les 5 derniers seulement."""

    @property
    def current_episode(self) -> Episode | None:
        return self.episodes[-1] if self.episodes else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ip": self.ip, "episodes": [e.to_dict() for e in self.episodes],
            "actions": [a.to_dict() for a in self.actions], "subject_ids": list(self.subject_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceHistory:
        return cls(
            ip=str(data["ip"]), episodes=tuple(Episode.from_dict(e) for e in data.get("episodes", ())),
            actions=tuple(PastAction.from_dict(a) for a in data.get("actions", ())),
            subject_ids=tuple(data.get("subject_ids", ())),
        )


def _is_activity(event: ObservedEvent) -> bool:
    return event.kind in ("attack", "decoy_hit")


def _last_action_end(history: SourceHistory) -> datetime | None:
    return max((a.ends_at for a in history.actions), default=None)


def apply_event(history: SourceHistory, event: ObservedEvent, *, episode_gap_seconds: int) -> tuple[SourceHistory, bool]:
    """Integre un evenement ; retourne (nouvel historique, vrai si un NOUVEL episode vient de commencer)."""
    subject_ids = history.subject_ids
    if event.subject_id and event.subject_id not in subject_ids:
        subject_ids = (*subject_ids, event.subject_id)[-5:]
    current = history.current_episode

    if event.kind == "blocklist_hit":
        if current is None:
            return replace(history, subject_ids=subject_ids), False
        updated = replace(current, blocklist_hits=current.blocklist_hits + 1)
        return replace(history, episodes=(*history.episodes[:-1], updated), subject_ids=subject_ids), False

    if event.kind == "threat_escalated":
        if current is None or event.level is None:
            return replace(history, subject_ids=subject_ids), False
        if current.max_level is None or LEVEL_RANK.get(event.level, -1) > LEVEL_RANK.get(current.max_level, -1):
            current = replace(current, max_level=event.level)
        return replace(history, episodes=(*history.episodes[:-1], current), subject_ids=subject_ids), False

    if not _is_activity(event):
        return replace(history, subject_ids=subject_ids), False

    gap = timedelta(seconds=episode_gap_seconds)
    last_action_end = _last_action_end(history)
    starts_new = (
        current is None
        or event.timestamp - current.last_seen_at > gap
        or (current.action_taken and last_action_end is not None and event.timestamp >= last_action_end)
    )
    classes = (event.attack_class,) if event.kind == "attack" and event.attack_class else ()
    if starts_new:
        episode = Episode(
            started_at=event.timestamp, last_seen_at=event.timestamp,
            attacks=1 if event.kind == "attack" else 0, attack_classes=classes,
            decoy_hits=1 if event.kind == "decoy_hit" else 0,
        )
        episodes = (*history.episodes, episode)[-MAX_EPISODES:]
        return replace(history, episodes=episodes, subject_ids=subject_ids), True
    assert current is not None
    merged_classes = current.attack_classes + tuple(c for c in classes if c not in current.attack_classes)
    episode = replace(
        current,
        last_seen_at=max(current.last_seen_at, event.timestamp),
        attacks=current.attacks + (1 if event.kind == "attack" else 0),
        attack_classes=merged_classes,
        decoy_hits=current.decoy_hits + (1 if event.kind == "decoy_hit" else 0),
    )
    return replace(history, episodes=(*history.episodes[:-1], episode), subject_ids=subject_ids), False


def record_action(history: SourceHistory, action: PastAction) -> SourceHistory:
    """Une action prise : comptee pour le palier, et l'episode en cours est marque (une seule par episode)."""
    episodes = history.episodes
    if episodes:
        episodes = (*episodes[:-1], replace(episodes[-1], action_taken=True))
    return replace(history, episodes=episodes, actions=(*history.actions, action)[-MAX_ACTIONS:])


def exclude_from_recidive(history: SourceHistory, action_id: str) -> SourceHistory:
    """« Ne pas compter dans la recidive » (faux positif) : l'action reste visible, le palier suivant
    ne la compte plus."""
    return replace(history, actions=tuple(
        replace(a, counts_for_recidive=False) if a.action_id == action_id else a for a in history.actions
    ))


def end_action(history: SourceHistory, action_id: str, ended_at: datetime) -> SourceHistory:
    """Action levee avant son echeance : la suite de l'activite de la source est un nouvel episode des
    maintenant, pas a l'echeance prevue."""
    return replace(history, actions=tuple(
        replace(a, ends_at=min(a.ends_at, ended_at)) if a.action_id == action_id else a for a in history.actions
    ))


def mark_episode_decided(history: SourceHistory) -> SourceHistory:
    """Decision prise mais aucune action appliquee (echec, ban plus fort deja en place) : l'episode en
    cours ne redecide plus, sans compter d'action pour le palier. Une action appliquee : `record_action`."""
    if not history.episodes:
        return history
    return replace(history, episodes=(*history.episodes[:-1], replace(history.episodes[-1], action_taken=True)))


def episodes_since(history: SourceHistory, since: datetime) -> int:
    return sum(1 for e in history.episodes if e.started_at >= since)


def next_tier_index(history: SourceHistory, now: datetime, *, recidive_window_seconds: int, tier_count: int) -> int:
    since = now - timedelta(seconds=recidive_window_seconds)
    previous = sum(1 for a in history.actions if a.counts_for_recidive and a.taken_at >= since)
    return min(previous, tier_count - 1)


def forget_before(history: SourceHistory, cutoff: datetime) -> SourceHistory:
    return replace(
        history,
        episodes=tuple(e for e in history.episodes if e.last_seen_at >= cutoff),
        actions=tuple(a for a in history.actions if a.ends_at >= cutoff),
    )
