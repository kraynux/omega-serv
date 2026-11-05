"""Application et levee des actions RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.6, lot 4).

Toujours par les mecanismes existants, jamais une seconde voie :
- ban local : la blocklist du WAF (`add_entry_unless_stronger`, sous le verrou du lot 0), entree
  `source: "riposte"` dont la raison porte l'identifiant de l'action ; levee par `remove_entry_if`,
  seulement si l'entree est encore celle de CETTE action (jamais un ban manuel ou du WAF) ;
- leurre : les affectations d'Active Defense (`assign_or_extend_deception`) ; levee seulement si
  l'affectation est encore celle posee par l'action (meme profil, meme echeance).

Ordre (etude §14) : l'action est enregistree `pending` AVANT l'appel, puis `applied` / `failed`. Un
arret brutal entre les deux laisse une action `pending`, tranchee par la reconciliation au demarrage
(`reconcile`). Aucune transaction SQLite n'est tenue pendant l'ecriture de la blocklist.

Ban reseau (lot 6) : `local_and_network_ban` pose le ban local puis ecrit une ligne dans
riposte-decisions.jsonl, lue par les jails omega-jail. Une levee ne retire QUE le ban local : omega-serv
n'a pas les droits sur fail2ban (l'interface dit ou lever le ban reseau)."""
from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from omega_serv.application.active_defense.manage_deception import assign_or_extend_deception
from omega_serv.domain.security.riposte.actions import (
    RiposteAction,
    action_id_from_reason,
    blocklist_reason,
)
from omega_serv.domain.security.riposte.decide import Decision
from omega_serv.domain.security.riposte.network_ban import network_ban_line
from omega_serv.domain.security.waf.blocklist import validate_blocklist_entry
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.deception_assignment_repository_port import DeceptionAssignmentRepositoryPort
from omega_serv.ports.riposte_store_port import RiposteStorePort


def new_action_id() -> str:
    return secrets.token_hex(6)


@dataclass(frozen=True)
class ActionTargets:
    """Ce sur quoi RIPOSTE peut agir. None = mecanisme indisponible (WAF ou Active Defense inactif) :
    l'action echoue avec un code explicite (« activer le WAF pour les actions de ban »)."""
    blocklist: BlocklistPort | None
    deception: DeceptionAssignmentRepositoryPort | None
    network_log: Callable[[str], None] | None = None
    """Ecrit une ligne dans riposte-decisions.jsonl (lot 6) ; None = journal du ban reseau desactive
    (`network_ban_log`). Le ban reseau n'est ecrit qu'APRES un ban local reussi."""


class RiposteActuator:
    def __init__(
        self,
        store: RiposteStorePort,
        targets: ActionTargets,
        *,
        new_id: Callable[[], str] = new_action_id,
    ) -> None:
        self._store = store
        self._targets = targets
        self._new_id = new_id

    def update_targets(self, targets: ActionTargets) -> None:
        self._targets = targets

    # --- Application --------------------------------------------------------------------------

    def apply(self, decision: Decision, subject_ids: tuple[str, ...], now: datetime) -> RiposteAction:
        assert decision.status == "matched" and decision.action and decision.policy_id and decision.duration_seconds
        action = RiposteAction(
            id=self._new_id(), ip=decision.ip, kind=decision.action, policy_id=decision.policy_id,
            created_at=now, ends_at=now + timedelta(seconds=decision.duration_seconds), state="pending",
            tier_index=decision.tier_index, decoy_profile=decision.decoy_profile,
            counts_for_recidive=decision.action != "decoy", event_id=decision.event_id,
        )
        self._store.save_action(action)
        try:
            if action.is_ban:
                result = self._apply_ban(action)
            else:
                result = self._apply_decoy(action, subject_ids, now)
        except OSError as error:
            result = replace(action, state="failed", detail=f"error:{type(error).__name__}")
        if result.state == "failed":
            result = replace(result, finished_at=now)
        self._store.save_action(result)
        return result

    def _apply_ban(self, action: RiposteAction) -> RiposteAction:
        blocklist = self._targets.blocklist
        if blocklist is None:
            return replace(action, state="failed", detail="waf_inactive")
        entry = BlocklistEntry(
            network=action.network, reason=blocklist_reason(action), created_at=action.created_at.isoformat(),
            expires_at=action.ends_at.isoformat(), source="riposte",
        )
        if validate_blocklist_entry(entry) is not None:
            return replace(action, state="failed", detail="invalid_network")
        if not blocklist.add_entry_unless_stronger(entry):
            return replace(action, state="failed", detail="stronger_ban_present")
        if action.kind == "local_and_network_ban" and self._targets.network_log is not None:
            self._targets.network_log(network_ban_line(
                at=action.created_at, ip=action.ip, action_id=action.id, policy_id=action.policy_id,
                tier_index=action.tier_index, duration_seconds=int((action.ends_at - action.created_at).total_seconds()),
            ))
        return replace(action, state="applied")

    def _apply_decoy(self, action: RiposteAction, subject_ids: tuple[str, ...], now: datetime) -> RiposteAction:
        deception = self._targets.deception
        if deception is None:
            return replace(action, state="failed", detail="active_defense_inactive")
        if not subject_ids:
            return replace(action, state="failed", detail="no_subject")
        assert action.decoy_profile is not None
        written = []
        for subject_id in subject_ids:
            assignment = assign_or_extend_deception(
                deception, subject_id=subject_id, profile_name=action.decoy_profile, until=action.ends_at, now=now,
            )
            if assignment is not None and assignment.expires_at == action.ends_at:
                written.append(subject_id)
        if not written:
            return replace(action, state="failed", detail="decoy_already_assigned")
        return replace(action, state="applied", subject_ids=tuple(written))

    # --- Verification et levee ----------------------------------------------------------------

    def is_in_place(self, action: RiposteAction, now: datetime) -> bool:
        """Vrai si l'action est encore reellement en place. Peut lever OSError (-> etat `unknown`)."""
        if action.is_ban:
            if self._targets.blocklist is None:
                return False
            return any(
                e.source == "riposte" and action_id_from_reason(e.reason) == action.id
                for e in self._targets.blocklist.list_entries()
            )
        if self._targets.deception is None:
            return False
        return any(self._is_ours(action, subject_id, now) for subject_id in action.subject_ids)

    def _is_ours(self, action: RiposteAction, subject_id: str, now: datetime) -> bool:
        assert self._targets.deception is not None
        current = self._targets.deception.get(subject_id)
        return (current is not None and now < current.expires_at and current.profile_name == action.decoy_profile
                and current.expires_at == action.ends_at)

    def revoke(self, action: RiposteAction, *, by: str, now: datetime) -> RiposteAction:
        """Leve l'action si elle est encore en place (et seulement ce qu'elle a pose). Idempotent."""
        if not action.in_progress:
            return action
        if action.is_ban:
            if self._targets.blocklist is not None:
                self._targets.blocklist.remove_entry_if(
                    action.network,
                    lambda e: e.source == "riposte" and action_id_from_reason(e.reason) == action.id,
                )
        elif self._targets.deception is not None:
            for subject_id in action.subject_ids:
                if self._is_ours(action, subject_id, now):
                    self._targets.deception.release(subject_id)
        revoked = replace(action, state="revoked", finished_at=now, finished_by=by)  # type: ignore[arg-type]
        self._store.save_action(revoked)
        return revoked

    # --- Reconciliation (demarrage + toutes les 60 s) -----------------------------------------

    def reconcile(self, now: datetime, limit: int = 10_000) -> dict[str, int]:
        """Pour chaque action en cours : echeance passee -> `expired` ; `pending` (arret brutal pendant
        l'application) -> `applied` si en place, sinon `failed` ; `applied` absente -> `revoked`
        (« retiree hors RIPOSTE ») ; verification impossible -> `unknown` (revue au tour suivant)."""
        counts: dict[str, int] = {}
        for action in self._store.list_actions(in_progress=True, limit=limit):
            if now >= action.ends_at:
                updated = replace(action, state="expired", finished_at=action.ends_at, finished_by="expiry")
            else:
                try:
                    in_place = self.is_in_place(action, now)
                except OSError:
                    updated = replace(action, state="unknown", detail="check_failed")
                else:
                    if in_place:
                        updated = replace(action, state="applied", detail="" if action.state == "unknown" else action.detail)
                    elif action.state == "pending":
                        updated = replace(action, state="failed", detail="interrupted", finished_at=now)
                    else:
                        updated = replace(action, state="revoked", detail="removed_outside", finished_at=now,
                                          finished_by="outside")
            if updated != action:
                self._store.save_action(updated)
                counts[updated.state] = counts.get(updated.state, 0) + 1
        return counts
