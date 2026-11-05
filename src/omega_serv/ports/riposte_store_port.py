"""Stockage du processus RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.8, lot 2) : positions de
lecture des journaux, evenements deja vus (dedoublonnage), etat (arret d'urgence, diagnostic) et
audit ; lot 3 : sources et decisions ; lot 4 : registre des actions, exemptions, commandes. Un seul
ecrivain : le processus RIPOSTE ; la TUI et la CLI lisent, et ne font que DEPOSER des commandes
(`add_command`) ou poser l'arret d'urgence (`set_state`)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from omega_serv.domain.security.riposte.actions import Exemption, RiposteAction, RiposteCommand
from omega_serv.domain.security.riposte.decide import Decision
from omega_serv.domain.security.riposte.history import SourceHistory


@dataclass(frozen=True)
class FollowerPosition:
    """Position de lecture d'un journal, memorisee entre deux demarrages."""
    inode: int
    device: int
    offset: int
    fingerprint: str
    """SHA-256 des `fingerprint_length` premiers octets du fichier lors de la derniere lecture."""
    fingerprint_length: int


class RiposteStorePort(Protocol):
    def close(self) -> None:
        ...

    def get_position(self, journal: str) -> FollowerPosition | None:
        ...

    def save_position(self, journal: str, position: FollowerPosition) -> None:
        ...

    def mark_seen(self, event_id: str, seen_at: datetime) -> bool:
        """Vrai si l'evenement est NOUVEAU (enregistre), faux s'il avait deja ete vu."""
        ...

    def purge_seen_before(self, cutoff: datetime) -> int:
        ...

    def get_state(self, key: str) -> str | None:
        ...

    def set_state(self, key: str, value: str) -> None:
        ...

    def append_audit(self, occurred_at: datetime, kind: str, detail: str) -> None:
        ...

    def purge_audit(self, before: datetime, max_rows: int) -> int:
        ...

    def get_source(self, ip: str) -> SourceHistory | None:
        ...

    def save_source(self, history: SourceHistory, updated_at: datetime) -> None:
        ...

    def list_sources(self, limit: int) -> list[tuple[SourceHistory, datetime]]:
        """Les plus recemment actives d'abord."""
        ...

    def purge_sources(self, before: datetime, max_rows: int) -> int:
        ...

    def append_decision(self, decision: Decision, applied: bool) -> None:
        ...

    def list_decisions(self, limit: int, ip: str | None = None) -> list[tuple[Decision, bool]]:
        """Les plus recentes d'abord ; (decision, appliquee)."""
        ...

    def purge_decisions(self, before: datetime, max_rows: int) -> int:
        ...

    # --- Lot 4 : registre des actions --------------------------------------------------------

    def save_action(self, action: RiposteAction) -> None:
        """Insere ou remplace (meme `id`)."""
        ...

    def get_action(self, action_id: str) -> RiposteAction | None:
        ...

    def list_actions(self, *, in_progress: bool, limit: int, ip: str | None = None,
                     policy_id: str | None = None) -> list[RiposteAction]:
        """En cours (pending, applied, unknown) ou terminees ; les plus recentes d'abord."""
        ...

    def count_in_progress(self, *, bans_only: bool, ip: str | None = None) -> int:
        ...

    def purge_finished_actions(self, before: datetime, max_rows: int) -> int:
        """Jamais une action en cours : seules les terminees vieillissent."""
        ...

    # --- Exemptions ajoutees par « Lever et exempter » -------------------------------------------

    def add_exemption(self, exemption: Exemption) -> None:
        ...

    def list_exemptions(self) -> list[Exemption]:
        ...

    def remove_exemption(self, network: str) -> bool:
        ...

    def purge_exemptions(self, now: datetime) -> int:
        """Retire les exemptions echues."""
        ...

    # --- Commandes de l'interface -------------------------------------------------------------

    def add_command(self, kind: str, params: dict[str, object], created_at: datetime) -> int:
        ...

    def pending_commands(self, limit: int) -> list[RiposteCommand]:
        """Les plus anciennes d'abord."""
        ...

    def get_command(self, command_id: int) -> RiposteCommand | None:
        ...

    def finish_command(self, command_id: int, *, state: str, result: str, result_params: dict[str, object],
                       done_at: datetime) -> None:
        ...

    def purge_commands(self, before: datetime, max_rows: int) -> int:
        ...

    def forget_source(self, ip: str) -> bool:
        ...
