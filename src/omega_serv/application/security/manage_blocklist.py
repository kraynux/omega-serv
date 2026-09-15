# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage de gestion de la blocklist (doc WAF, menu CLI "Gestion
blocklist"). Un bannissement permanent (`expires_at=None`) exige une
confirmation explicite de l'appelant (doc WAF §5, "Politique
recommandee" : "bannissement permanent uniquement depuis le CLI, avec
confirmation") - ce module refuse d'en creer un sans `confirm_permanent=True`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from omega_serv.domain.security.waf.blocklist import validate_blocklist_entry
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.ports.blocklist_port import BlocklistPort


@dataclass(frozen=True)
class ManageBlocklistResult:
    success: bool
    message: str


def add_blocklist_entry(
    blocklist_port: BlocklistPort,
    network: str,
    reason: str,
    duration_seconds: int | None,
    confirm_permanent: bool = False,
) -> ManageBlocklistResult:
    now = datetime.now(timezone.utc)
    if duration_seconds is None and not confirm_permanent:
        return ManageBlocklistResult(
            False,
            "Bannissement permanent refuse sans confirmation explicite "
            "(passer --duration-seconds, ou --confirm-permanent pour un bannissement sans expiration).",
        )

    expires_at = None if duration_seconds is None else (now + timedelta(seconds=duration_seconds)).isoformat()
    entry = BlocklistEntry(network=network, reason=reason, created_at=now.isoformat(), expires_at=expires_at, source="manual")

    error = validate_blocklist_entry(entry)
    if error is not None:
        return ManageBlocklistResult(False, error)

    blocklist_port.add_entry(entry)
    return ManageBlocklistResult(True, f"Entree ajoutee : {network} ({'permanent' if expires_at is None else f'expire {expires_at}'})")


def remove_blocklist_entry(blocklist_port: BlocklistPort, network: str) -> ManageBlocklistResult:
    removed = blocklist_port.remove_entry(network)
    if not removed:
        return ManageBlocklistResult(False, f"Aucune entree pour {network}")
    return ManageBlocklistResult(True, f"Entree retiree : {network}")
